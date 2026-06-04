"""Central synthesis contracts for round-based deliberation."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from trinity.deliberation.consensus import ConsensusEngine
from trinity.models import ConsensusResult, Provider, ResponseStatus
from trinity.providers.invoker import PromptRequest, ProviderInvoker
from trinity.providers.policy import InvocationAccess
from trinity.workflow.models import Blueprint, DecisionRecord, OpenQuestion
from trinity.workflow.structured import (
    StructuredConsensusResult,
    StructuredConsensusSynthesizer,
    StructuredVote,
    VoteType,
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


class SynthesisValidationError(ValueError):
    """Raised when provider-backed synthesis cannot produce a valid result."""


class ModelBackedSynthesisAgent:
    """Central synthesis implementation backed by a one-shot provider call."""

    def __init__(
        self,
        *,
        invoker: ProviderInvoker,
        agent_name: str,
        provider: Provider,
        cli_command: str,
        cwd: Path,
        env: dict[str, str] | None = None,
        model: str = "default",
        requested_model: str = "fast",
        extra_args: tuple[str, ...] = (),
        timeout_seconds: float = 300.0,
        max_input_chars: int = 60_000,
        artifact_dir: Path | None = None,
        lang: str = "en",
    ):
        self.invoker = invoker
        self.agent_name = agent_name
        self.provider = provider
        self.cli_command = cli_command
        self.cwd = cwd
        self.env = dict(env or {})
        self.model = model or "default"
        self.requested_model = requested_model or self.model
        self.extra_args = tuple(extra_args)
        self.timeout_seconds = timeout_seconds
        self.max_input_chars = max_input_chars
        self.artifact_dir = artifact_dir
        self.lang = lang

    async def synthesize(self, synthesis_input: SynthesisInput) -> SynthesisResult:
        """Call a provider and convert its strict JSON response into SynthesisResult."""
        request_id = f"synthesis-round-{synthesis_input.round_num}-{uuid4().hex[:12]}"
        prompt = self._build_prompt(synthesis_input)
        request = PromptRequest(
            agent_name=self.agent_name,
            provider=self.provider,
            cli_command=self.cli_command,
            prompt=prompt,
            cwd=self.cwd,
            timeout_seconds=self.timeout_seconds,
            request_id=request_id,
            role_prompt=self._role_prompt(),
            round_num=synthesis_input.round_num,
            env=dict(self.env),
            model=self.model,
            extra_args=self.extra_args,
            access=InvocationAccess.READ_ONLY,
        )
        turn = await self.invoker.invoke(request)
        raw_output = turn.raw_output or turn.content
        provider_diagnostics = list(turn.diagnostics)

        if turn.status != ResponseStatus.OK:
            artifacts = self._write_artifacts(
                synthesis_input.round_num,
                raw_output=raw_output,
                parsed_payload=None,
                diagnostics=provider_diagnostics,
            )
            detail = f"model synthesis provider returned {turn.status.value}"
            if provider_diagnostics:
                detail = f"{detail}: {'; '.join(provider_diagnostics)}"
            if artifacts:
                detail = f"{detail} (artifacts: {artifacts})"
            raise SynthesisValidationError(detail)

        try:
            payload = self._extract_json_object(turn.content or raw_output)
        except SynthesisValidationError as exc:
            self._write_artifacts(
                synthesis_input.round_num,
                raw_output=raw_output,
                parsed_payload=None,
                diagnostics=[str(exc), *provider_diagnostics],
            )
            raise

        try:
            result = self._result_from_payload(synthesis_input, payload)
        except SynthesisValidationError as exc:
            self._write_artifacts(
                synthesis_input.round_num,
                raw_output=raw_output,
                parsed_payload=payload,
                diagnostics=[str(exc), *provider_diagnostics],
            )
            raise

        artifacts = self._write_artifacts(
            synthesis_input.round_num,
            raw_output=raw_output,
            parsed_payload=payload,
            diagnostics=[*result.diagnostics, *provider_diagnostics],
        )
        result.metadata.update(
            {
                "fallback_used": False,
                "provider": self.provider.value,
                "provider_agent": self.agent_name,
                "model": self.model,
                "requested_model": self.requested_model,
                "status": turn.status.value,
                "elapsed_seconds": turn.elapsed_seconds,
                "request_id": request_id,
            }
        )
        if provider_diagnostics:
            result.metadata["provider_diagnostics"] = provider_diagnostics
        result.metadata.update(artifacts)
        return result

    def _role_prompt(self) -> str:
        prompt = (
            "You are Trinity's central synthesis coordinator. Normalize the "
            "agent opinions into the requested JSON schema. Return only one "
            "JSON object and no Markdown, prose, or code fences."
        )
        if self.lang == "ko":
            prompt += (
                " All user-facing string values must be Korean, including "
                "summary_for_shared_md, next_round_prompt, questions, options, "
                "recommendations, rationales, blueprint fields, risks, and "
                "acceptance criteria."
            )
        return prompt

    def _build_prompt(self, synthesis_input: SynthesisInput) -> str:
        schema = {
            "consensus_reached": "boolean",
            "agreement_count": "integer",
            "total_agents": "integer matching usable_agent_opinions count",
            "summary_for_shared_md": "non-empty string",
            "next_round_prompt": "string",
            "open_questions_for_user": [
                {
                    "id": "string",
                    "question": "string",
                    "options": ["string"],
                    "recommended_option": "string or null",
                    "blocking": "boolean",
                    "raised_by": ["agent name"],
                    "rationale": "string",
                }
            ],
            "recommended_blueprint": {
                "title": "string",
                "summary": "string",
                "architecture": [
                    {
                        "name": "string",
                        "responsibility": "string",
                        "owner_agent": "string or null",
                        "dependencies": ["string"],
                    }
                ],
                "data_flow": ["string"],
                "external_dependencies": ["string"],
                "risks": [
                    {
                        "description": "string",
                        "severity": "low|medium|high",
                        "mitigation": "string",
                        "owner_agent": "string or null",
                    }
                ],
                "acceptance_criteria": ["string"],
                "open_questions": [],
            },
            "votes": {
                "agent_name": {
                    "vote": "approve|approve_with_changes|blocked_by_question|reject",
                    "rationale": "string",
                }
            },
            "diagnostics": ["string"],
        }
        payload = {
            "original_user_prompt": synthesis_input.user_prompt,
            "round_number": synthesis_input.round_num,
            "previous_synthesis_summary": synthesis_input.previous_summary,
            "recorded_user_decisions": [
                decision.to_dict() for decision in synthesis_input.decisions
            ],
            "pending_open_questions": [
                question.to_dict() for question in synthesis_input.open_questions
            ],
            "usable_agent_opinions": self._bounded_opinions(synthesis_input.opinions),
            "invalid_response_diagnostics": synthesis_input.metadata.get(
                "invalid_response_diagnostics",
                [],
            ),
            "rules": [
                self._language_rule(),
                "summary_for_shared_md must be non-empty.",
                "total_agents must equal the usable_agent_opinions count.",
                "If open_questions_for_user is non-empty, consensus_reached must be false.",
                "If there is no valid recommended_blueprint, consensus_reached must be false.",
                "Do not invent provider names outside usable_agent_opinions.",
            ],
            "output_schema": schema,
        }
        return (
            "Return exactly one JSON object matching output_schema.\n\n"
            + json.dumps(payload, ensure_ascii=False, indent=2)
        )

    def _language_rule(self) -> str:
        if self.lang == "ko":
            return (
                "All user-facing string values must be Korean. Keep only JSON "
                "field names and enum values in English."
            )
        return "Use English for user-facing string values unless the user requested another language."

    def _bounded_opinions(self, opinions: dict[str, str]) -> dict[str, str]:
        if not opinions:
            return {}
        per_opinion = max(1_000, self.max_input_chars // max(1, len(opinions)))
        bounded: dict[str, str] = {}
        for agent, opinion in opinions.items():
            text = str(opinion)
            if len(text) > per_opinion:
                text = text[:per_opinion].rstrip() + "\n[truncated]"
            bounded[agent] = text
        return bounded

    @staticmethod
    def _extract_json_object(text: str) -> dict[str, Any]:
        decoder = json.JSONDecoder()
        source = str(text or "")
        for index, char in enumerate(source):
            if char != "{":
                continue
            try:
                value, _ = decoder.raw_decode(source[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
        raise SynthesisValidationError("model synthesis returned no JSON object")

    def _result_from_payload(
        self,
        synthesis_input: SynthesisInput,
        payload: dict[str, Any],
    ) -> SynthesisResult:
        if not isinstance(payload, dict):
            raise SynthesisValidationError("model synthesis JSON root is not an object")

        summary = str(payload.get("summary_for_shared_md") or "").strip()
        if not summary:
            raise SynthesisValidationError("summary_for_shared_md is empty")

        expected_total = len(synthesis_input.opinions)
        total_agents = self._coerce_int(payload.get("total_agents"), "total_agents")
        if total_agents != expected_total:
            raise SynthesisValidationError(
                f"total_agents {total_agents} does not match usable opinions {expected_total}"
            )
        agreement_count = self._coerce_int(
            payload.get("agreement_count"),
            "agreement_count",
        )
        if agreement_count < 0 or agreement_count > total_agents:
            raise SynthesisValidationError("agreement_count is outside total_agents range")

        raw_diagnostics = payload.get("diagnostics", []) or []
        if not isinstance(raw_diagnostics, list):
            raw_diagnostics = [raw_diagnostics]
        diagnostics = [str(item) for item in raw_diagnostics if str(item).strip()]
        open_questions = self._open_questions_from_payload(
            payload.get("open_questions_for_user", []),
            round_num=synthesis_input.round_num,
        )
        blueprint = self._blueprint_from_payload(payload.get("recommended_blueprint"))
        consensus_reached = self._coerce_bool(payload.get("consensus_reached"))

        if open_questions and consensus_reached:
            consensus_reached = False
            diagnostics.append("consensus normalized false because open questions exist")
        if blueprint is not None and not blueprint.is_valid:
            blueprint = None
            consensus_reached = False
            diagnostics.append("consensus normalized false because blueprint is invalid")
        if consensus_reached and blueprint is None:
            consensus_reached = False
            diagnostics.append("consensus normalized false because blueprint is missing")

        votes, vote_count, vote_opinions = self._structured_votes_from_payload(
            payload.get("votes", {}),
            synthesis_input=synthesis_input,
            agreement_count=agreement_count,
            blueprint=blueprint,
            open_questions=open_questions,
        )
        consensus = ConsensusResult(
            reached=consensus_reached,
            agreement_count=agreement_count,
            total_agents=total_agents,
            opinions=vote_opinions,
            summary=summary,
        )
        structured = StructuredConsensusResult(
            reached=consensus_reached,
            vote_count=vote_count,
            final_blueprint=blueprint if consensus_reached else None,
            open_questions=open_questions,
            blockers=[],
            votes=votes,
            summary=summary,
        )
        return SynthesisResult(
            round_num=synthesis_input.round_num,
            consensus_reached=consensus_reached,
            agreement_count=agreement_count,
            total_agents=total_agents,
            summary_for_shared_md=summary,
            next_round_prompt=str(payload.get("next_round_prompt") or ""),
            open_questions_for_user=open_questions,
            decisions=self._decisions_from_payload(payload.get("decisions", [])),
            recommended_blueprint=blueprint,
            consensus=consensus,
            structured_consensus=structured,
            source="model-backed",
            diagnostics=diagnostics,
        )

    def _structured_votes_from_payload(
        self,
        payload: Any,
        *,
        synthesis_input: SynthesisInput,
        agreement_count: int,
        blueprint: Blueprint | None,
        open_questions: list[OpenQuestion],
    ) -> tuple[dict[str, StructuredVote], dict[VoteType, int], dict[str, str]]:
        vote_payload = payload if isinstance(payload, dict) else {}
        vote_count = {vote_type: 0 for vote_type in VoteType}
        votes: dict[str, StructuredVote] = {}
        vote_opinions: dict[str, str] = {}

        for index, agent_name in enumerate(synthesis_input.opinions):
            raw_vote = vote_payload.get(agent_name, {})
            raw_vote = raw_vote if isinstance(raw_vote, dict) else {}
            default_vote = (
                VoteType.APPROVE if index < agreement_count else VoteType.REJECT
            )
            vote_type = self._parse_vote(raw_vote.get("vote"), default_vote)
            rationale = str(raw_vote.get("rationale") or vote_type.value)
            agent_questions = [
                question
                for question in open_questions
                if agent_name in question.raised_by
            ]
            vote = StructuredVote(
                agent_name=agent_name,
                vote=vote_type,
                rationale=rationale,
                blueprint=blueprint if vote_type != VoteType.REJECT else None,
                open_questions=agent_questions,
                blockers=[],
            )
            votes[agent_name] = vote
            vote_count[vote_type] += 1
            vote_opinions[agent_name] = rationale

        return votes, vote_count, vote_opinions

    @staticmethod
    def _parse_vote(value: Any, default: VoteType) -> VoteType:
        if value is None:
            return default
        normalized = str(value).strip().lower().replace("-", "_")
        try:
            return VoteType(normalized)
        except ValueError:
            return default

    @classmethod
    def _open_questions_from_payload(
        cls,
        payload: Any,
        *,
        round_num: int,
    ) -> list[OpenQuestion]:
        if payload in (None, ""):
            return []
        if not isinstance(payload, list):
            raise SynthesisValidationError("open_questions_for_user must be a list")
        questions: list[OpenQuestion] = []
        for index, item in enumerate(payload, start=1):
            if not isinstance(item, dict):
                raise SynthesisValidationError("open question item must be an object")
            data = cls._normalize_question_data(item)
            if not data.get("id"):
                data["id"] = f"round-{round_num}-q-{index:03d}"
            question = OpenQuestion.from_dict(data)
            if not question.question.strip():
                raise SynthesisValidationError("open question text is empty")
            questions.append(question)
        return questions

    @classmethod
    def _normalize_question_data(cls, data: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(data)
        options = normalized.get("options", [])
        if options is None:
            options = []
        elif isinstance(options, str):
            delimiter = "|" if "|" in options else ","
            options = [part.strip() for part in options.split(delimiter)]
        elif not isinstance(options, list):
            options = [options]
        normalized["options"] = [str(option) for option in options if str(option).strip()]
        raised_by = normalized.get("raised_by", [])
        if raised_by is None:
            raised_by = []
        elif isinstance(raised_by, str):
            raised_by = [raised_by]
        normalized["raised_by"] = [str(item) for item in raised_by if str(item).strip()]
        normalized["blocking"] = cls._coerce_bool(normalized.get("blocking", True))
        return normalized

    @classmethod
    def _blueprint_from_payload(cls, payload: Any) -> Blueprint | None:
        if payload in (None, ""):
            return None
        if not isinstance(payload, dict):
            raise SynthesisValidationError("recommended_blueprint must be an object")
        data = dict(payload)
        data["architecture"] = cls._normalize_architecture(data.get("architecture", []))
        data["risks"] = cls._normalize_risks(data.get("risks", []))
        data["open_questions"] = [
            cls._normalize_question_data(item)
            for item in data.get("open_questions", [])
            if isinstance(item, dict)
        ]
        return Blueprint.from_dict(data)

    @staticmethod
    def _normalize_architecture(payload: Any) -> list[dict[str, Any]]:
        items = payload if isinstance(payload, list) else []
        normalized: list[dict[str, Any]] = []
        for item in items:
            if isinstance(item, dict):
                normalized.append(item)
            elif str(item).strip():
                text = str(item).strip()
                normalized.append({"name": text, "responsibility": text})
        return normalized

    @staticmethod
    def _normalize_risks(payload: Any) -> list[dict[str, Any]]:
        items = payload if isinstance(payload, list) else []
        normalized: list[dict[str, Any]] = []
        for item in items:
            if isinstance(item, dict):
                normalized.append(item)
            elif str(item).strip():
                normalized.append({"description": str(item).strip()})
        return normalized

    @staticmethod
    def _decisions_from_payload(payload: Any) -> list[DecisionRecord]:
        if not isinstance(payload, list):
            return []
        return [
            DecisionRecord.from_dict(item)
            for item in payload
            if isinstance(item, dict) and str(item.get("decision", "")).strip()
        ]

    @staticmethod
    def _coerce_int(value: Any, field_name: str) -> int:
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise SynthesisValidationError(f"{field_name} must be an integer") from exc

    @staticmethod
    def _coerce_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y"}
        return bool(value)

    def _write_artifacts(
        self,
        round_num: int,
        *,
        raw_output: str,
        parsed_payload: dict[str, Any] | None,
        diagnostics: list[str],
    ) -> dict[str, str]:
        if self.artifact_dir is None:
            return {}
        round_dir = self.artifact_dir / f"round-{round_num:02d}"
        round_dir.mkdir(parents=True, exist_ok=True)
        raw_path = round_dir / "synthesis.raw.txt"
        raw_path.write_text(str(raw_output), encoding="utf-8")
        artifacts = {"raw_output_path": str(raw_path)}
        if parsed_payload is not None:
            json_path = round_dir / "synthesis.json"
            json_path.write_text(
                json.dumps(parsed_payload, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            artifacts["json_path"] = str(json_path)
        clean_diagnostics = [item for item in diagnostics if str(item).strip()]
        if clean_diagnostics:
            diagnostics_path = round_dir / "synthesis.diagnostics.txt"
            diagnostics_path.write_text("\n".join(clean_diagnostics), encoding="utf-8")
            artifacts["diagnostics_path"] = str(diagnostics_path)
        return artifacts

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
            result.metadata["fallback_reason"] = str(exc)
            return result
