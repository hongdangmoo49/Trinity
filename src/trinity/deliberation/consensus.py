"""Consensus engine — detect when agents have reached agreement."""

from __future__ import annotations

import logging
import re

from trinity.models import ConsensusResult

logger = logging.getLogger(__name__)


# Negation patterns that indicate disagreement despite containing "agree"
NEGATION_PATTERNS = [
    r"\bnot\s+agree",
    r"\bdon'?t\s+agree",
    r"\bdo\s+not\s+agree",
    r"\bdisagree",
    r"\bcan'?t\s+agree",
    r"\bcannot\s+agree",
    r"\bwon'?t\s+agree",
    r"\brefuse\s+to\s+agree",
    r"\bnever\s+agree",
    r"\bno\s+agreement",
    r"\bnot\s+in\s+agreement",
    r"\bdisapprove",
    r"\boppose",
    r"\bobject",
    r"\breject",
    r"\bagainst\s+(?:this|that|the|it)",
]


class ConsensusEngine:
    """Keyword-based consensus detection with negation awareness.

    Checks if agents' opinions contain agreement signals while
    filtering out negated forms like "I disagree" or "I don't agree".

    Phase 3 improvement: negation filtering eliminates false positives.
    Future: optional LLM or embedding similarity for higher accuracy.
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

        # Compile agreement pattern
        self._pattern = re.compile(
            "|".join(re.escape(kw) for kw in self.keywords),
            re.IGNORECASE,
        )

        # Compile negation patterns
        self._negation_pattern = re.compile(
            "|".join(f"({p})" for p in NEGATION_PATTERNS),
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
        """Check if text contains agreement keywords without negation.

        Two-step check:
        1. Find all agreement keyword matches
        2. For each match, verify it's not in a negated context
        """
        # First check if any agreement keyword exists at all
        if not self._pattern.search(text):
            return False

        # Check for negation — if negated, the agreement is overridden
        if self._negation_pattern.search(text):
            # Has negation, but might still have positive agreement elsewhere.
            # Check if there's agreement OUTSIDE of negated sentences.
            return self._has_positive_agreement(text)

        return True

    def _has_positive_agreement(self, text: str) -> bool:
        """Check if text has agreement that is NOT negated.

        Splits text into sentences and checks each independently.
        A sentence with negation doesn't count, but other sentences might.
        """
        # Split on sentence boundaries
        sentences = re.split(r'[.!?]\s*', text)

        for sentence in sentences:
            has_agreement = self._pattern.search(sentence) is not None
            has_negation = self._negation_pattern.search(sentence) is not None

            if has_agreement and not has_negation:
                return True

        return False

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
