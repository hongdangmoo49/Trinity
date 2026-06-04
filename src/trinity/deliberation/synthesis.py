"""Central synthesis contracts for round-based deliberation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from trinity.deliberation.consensus import ConsensusEngine
from trinity.models import ConsensusResult
from trinity.workflow.models import Blueprint, DecisionRecord, OpenQuestion
from trinity.workflow.structured import (
    StructuredConsensusResult,
    StructuredConsensusSynthesizer,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SynthesisInput:
    """Input given to the central synthesis step after a provider round."""

    user_prompt: str
    round_num: int
    opinions: dict[str, str]
    previous_summary: str = ""
    open_questions: list[OpenQuestion] = field(default_factory=list)
    decisions: list[DecisionRecord] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SynthesisResult:
    """Canonical synthesis result consumed by deliberation and workflow."""

    round_num: int
    consensus_reached: bool
    agreement_count: int
    total_agents: int
    summary_for_shared_md: str
    next_round_prompt: str = ""
    open_questions_for_user: list[OpenQuestion] = field(default_factory=list)
    decisions: list[DecisionRecord] = field(default_factory=list)
    recommended_blueprint: Blueprint | None = None
    consensus: ConsensusResult | None = None
    structured_consensus: StructuredConsensusResult | None = None
    source: str = "heuristic"
    diagnostics: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable synthesis payload."""
        return {
            "round_num": self.round_num,
            "consensus_reached": self.consensus_reached,
            "agreement_count": self.agreement_count,
            "total_agents": self.total_agents,
            "summary_for_shared_md": self.summary_for_shared_md,
            "next_round_prompt": self.next_round_prompt,
            "open_questions_for_user": [
                question.to_dict() for question in self.open_questions_for_user
            ],
            "decisions": [decision.to_dict() for decision in self.decisions],
            "recommended_blueprint": (
                self.recommended_blueprint.to_dict()
                if self.recommended_blueprint
                else None
            ),
            "consensus": (
                {
                    "reached": self.consensus.reached,
                    "agreement_count": self.consensus.agreement_count,
                    "total_agents": self.consensus.total_agents,
                    "opinions": dict(self.consensus.opinions),
                    "summary": self.consensus.summary,
                    "fraction": self.consensus.fraction,
                }
                if self.consensus
                else None
            ),
            "structured_consensus": (
                self.structured_consensus.to_dict()
                if self.structured_consensus
                else None
            ),
            "source": self.source,
            "diagnostics": list(self.diagnostics),
            "metadata": dict(self.metadata),
        }


class SynthesisAgent(Protocol):
    """Central round synthesizer interface."""

    async def synthesize(self, synthesis_input: SynthesisInput) -> SynthesisResult:
        """Produce one canonical synthesis result for a completed round."""


class HeuristicSynthesisAgent:
    """Synthesis implementation backed by existing deterministic parsers."""

    def __init__(
        self,
        consensus_engine: ConsensusEngine | None = None,
        structured_synthesizer: StructuredConsensusSynthesizer | None = None,
    ):
        self.consensus_engine = consensus_engine or ConsensusEngine()
        self.structured_synthesizer = (
            structured_synthesizer
            or StructuredConsensusSynthesizer(
                required_fraction=self.consensus_engine.required_fraction,
            )
        )

    async def synthesize(self, synthesis_input: SynthesisInput) -> SynthesisResult:
        """Evaluate structured consensus first, then legacy keyword consensus."""
        structured = self.structured_synthesizer.evaluate(synthesis_input.opinions)
        if structured.open_questions:
            consensus = self._consensus_from_structured(structured)
            return self._result_from_consensus(
                synthesis_input=synthesis_input,
                consensus=consensus,
                structured=structured,
                open_questions=structured.open_questions,
                next_round_prompt="Wait for user decisions before continuing.",
            )

        if structured.reached:
            consensus = self._consensus_from_structured(structured)
            return self._result_from_consensus(
                synthesis_input=synthesis_input,
                consensus=consensus,
                structured=structured,
                recommended_blueprint=structured.final_blueprint,
            )

        consensus = self.consensus_engine.evaluate(synthesis_input.opinions)
        return self._result_from_consensus(
            synthesis_input=synthesis_input,
            consensus=consensus,
            structured=structured,
            next_round_prompt=(
                "Ask each agent to compare the previous answers, resolve "
                "disagreements, and either produce a final blueprint or raise "
                "specific user-facing questions."
                if not consensus.reached
                else ""
            ),
        )

    def _result_from_consensus(
        self,
        *,
        synthesis_input: SynthesisInput,
        consensus: ConsensusResult,
        structured: StructuredConsensusResult | None,
        open_questions: list[OpenQuestion] | None = None,
        recommended_blueprint: Blueprint | None = None,
        next_round_prompt: str = "",
    ) -> SynthesisResult:
        return SynthesisResult(
            round_num=synthesis_input.round_num,
            consensus_reached=consensus.reached,
            agreement_count=consensus.agreement_count,
            total_agents=consensus.total_agents,
            summary_for_shared_md=consensus.summary,
            next_round_prompt=next_round_prompt,
            open_questions_for_user=list(open_questions or []),
            recommended_blueprint=recommended_blueprint,
            consensus=consensus,
            structured_consensus=structured,
            source="heuristic",
        )

    @staticmethod
    def _consensus_from_structured(
        structured: StructuredConsensusResult,
    ) -> ConsensusResult:
        """Convert structured consensus into the legacy result shape."""
        return ConsensusResult(
            reached=structured.reached,
            agreement_count=structured.approval_count,
            total_agents=structured.total_votes,
            opinions={
                name: vote.rationale or vote.vote.value
                for name, vote in structured.votes.items()
            },
            summary=structured.summary,
        )


class FallbackSynthesisAgent:
    """Try a primary synthesizer and fall back to a deterministic synthesizer."""

    def __init__(
        self,
        primary: SynthesisAgent,
        fallback: SynthesisAgent | None = None,
    ):
        self.primary = primary
        self.fallback = fallback or HeuristicSynthesisAgent()

    async def synthesize(self, synthesis_input: SynthesisInput) -> SynthesisResult:
        try:
            return await self.primary.synthesize(synthesis_input)
        except Exception as exc:
            logger.warning("Primary synthesis agent failed; using fallback: %s", exc)
            result = await self.fallback.synthesize(synthesis_input)
            result.diagnostics.append(f"primary synthesis failed: {exc}")
            result.metadata["fallback_used"] = True
            return result
