"""Consensus engine — detect when agents have reached agreement."""

from __future__ import annotations

import logging
import re

from trinity.models import ConsensusResult

logger = logging.getLogger(__name__)


class ConsensusEngine:
    """Keyword-based consensus detection.

    Checks if agents' opinions contain agreement signals.
    Phase 1: simple keyword counting. Phase 3+: optional LLM or embedding similarity.
    """

    DEFAULT_KEYWORDS = [
        "agree",
        "consensus",
        "approve",
        "동의",
        "합의",
        "approved",
        "agreed",
        "i agree",
        "we agree",
        "concur",
    ]

    def __init__(
        self,
        consensus_keywords: list[str] | None = None,
        required_fraction: float = 0.6,
    ):
        self.keywords = consensus_keywords or self.DEFAULT_KEYWORDS
        self.required_fraction = required_fraction
        # Compile regex for efficiency
        self._pattern = re.compile(
            "|".join(re.escape(kw) for kw in self.keywords),
            re.IGNORECASE,
        )

    def evaluate(self, opinions: dict[str, str]) -> ConsensusResult:
        """Evaluate whether agents have reached consensus.

        Args:
            opinions: {agent_name: opinion_text}

        Returns:
            ConsensusResult with reached=True if enough agents agree.
        """
        if not opinions:
            return ConsensusResult(
                reached=False,
                agreement_count=0,
                total_agents=0,
                opinions=opinions,
                summary="No opinions to evaluate.",
            )

        total = len(opinions)
        agreeing_agents: list[str] = []

        for agent, text in opinions.items():
            if self._contains_agreement(text):
                agreeing_agents.append(agent)

        agreement_count = len(agreeing_agents)
        fraction = agreement_count / total
        reached = fraction >= self.required_fraction

        summary = self._build_summary(reached, agreeing_agents, opinions)

        logger.info(
            f"Consensus evaluation: {agreement_count}/{total} agree "
            f"({fraction:.0%}) — {'REACHED' if reached else 'not reached'}"
        )

        return ConsensusResult(
            reached=reached,
            agreement_count=agreement_count,
            total_agents=total,
            opinions=opinions,
            summary=summary,
        )

    def _contains_agreement(self, text: str) -> bool:
        """Check if text contains agreement keywords."""
        return bool(self._pattern.search(text))

    def _build_summary(
        self,
        reached: bool,
        agreeing: list[str],
        opinions: dict[str, str],
    ) -> str:
        """Build a human-readable consensus summary."""
        if reached:
            return f"Consensus reached. Agreeing: {', '.join(agreeing)}."
        else:
            return (
                f"Consensus not reached ({len(agreeing)}/{len(opinions)} agree). "
                f"Need another round of deliberation."
            )
