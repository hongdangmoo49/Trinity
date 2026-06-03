"""Consensus engine — detect when agents have reached agreement."""

from __future__ import annotations

import logging
import re

from trinity.models import ConsensusResult, OpenQuestion, StructuredConsensusResult, VoteType

logger = logging.getLogger(__name__)


# Negation patterns that indicate disagreement despite containing "agree"
NEGATION_PATTERNS = [
    # English
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
    # Korean negation
    r"동의하지\s*않",
    r"동의할\s*수\s*없",
    r"합의하지\s*않",
    r"합의할\s*수\s*없",
    r"반대",
    r"거부",
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
        usable_opinions = {
            agent: text
            for agent, text in opinions.items()
            if self._is_usable_opinion(text)
        }

        if not usable_opinions:
            return ConsensusResult(
                reached=False,
                agreement_count=0,
                total_agents=0,
                opinions={},
                summary="No usable consensus: no valid agent opinions to evaluate.",
            )

        total = len(usable_opinions)
        agreeing_agents: list[str] = []

        for agent, text in usable_opinions.items():
            if self._contains_agreement(text):
                agreeing_agents.append(agent)

        agreement_count = len(agreeing_agents)
        fraction = agreement_count / total
        reached = fraction >= self.required_fraction

        summary = self._build_summary(reached, agreeing_agents, usable_opinions)

        logger.info(
            f"Consensus evaluation: {agreement_count}/{total} agree "
            f"({fraction:.0%}) — {'REACHED' if reached else 'not reached'}"
        )

        return ConsensusResult(
            reached=reached,
            agreement_count=agreement_count,
            total_agents=total,
            opinions=usable_opinions,
            summary=summary,
        )

    def _is_usable_opinion(self, text: str) -> bool:
        """Return whether a raw opinion text can participate in consensus."""
        if not text or not text.strip():
            return False

        normalized = text.strip().lower()
        unusable_prefixes = (
            "[invalid response omitted:",
            "[timeout after ",
            "[error:",
        )
        return not normalized.startswith(unusable_prefixes)

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
            # Extract key content from opinions for a meaningful summary
            key_points = self._extract_key_points(opinions)
            if key_points:
                return (
                    f"Consensus reached ({len(agreeing)}/{len(opinions)} agree). "
                    f"Key points: {key_points}"
                )
            return f"Consensus reached. Agreeing: {', '.join(agreeing)}."
        else:
            return (
                f"Consensus not reached ({len(agreeing)}/{len(opinions)} agree). "
                f"Need another round of deliberation."
            )

    def _extract_key_points(self, opinions: dict[str, str]) -> str:
        """Extract key points from agent opinions for summary.

        Takes the first opinion and truncates to a reasonable length.
        """
        if not opinions:
            return ""

        # Use the first opinion as representative
        for text in opinions.values():
            # Clean and truncate
            clean = text.strip()
            # Take first meaningful sentence(s), up to 200 chars
            if len(clean) > 200:
                # Truncate at last sentence boundary within limit
                truncated = clean[:200]
                last_period = truncated.rfind(".")
                if last_period > 50:
                    clean = truncated[: last_period + 1]
                else:
                    clean = truncated + "..."
            return clean

        return ""


# ---------------------------------------------------------------------------
# Structured Consensus Engine (v0.7.0)
# ---------------------------------------------------------------------------


class StructuredConsensusEngine:
    """Explicit vote-based consensus detection using VOTE: lines.

    Agents cast structured votes via ``VOTE: APPROVE`` (or Korean aliases).
    This replaces the keyword-guessing approach with an unambiguous protocol.

    Consensus is reached when:
    - positive votes (APPROVE + APPROVE_WITH_CHANGES) >= 60% of total, AND
    - no open questions remain, AND
    - no blockers exist.
    """

    VOTE_PATTERN = re.compile(
        r"(?:VOTE|투표)\s*:\s*"
        r"(APPROVE_WITH_CHANGES|BLOCKED_BY_QUESTION|APPROVE|REJECT"
        r"|수정승인|질문차단|승인|거부)",
        re.IGNORECASE,
    )

    VOTE_ALIASES: dict[str, VoteType] = {
        "APPROVE": VoteType.APPROVE,
        "APPROVE_WITH_CHANGES": VoteType.APPROVE_WITH_CHANGES,
        "BLOCKED_BY_QUESTION": VoteType.BLOCKED_BY_QUESTION,
        "REJECT": VoteType.REJECT,
        "승인": VoteType.APPROVE,
        "수정승인": VoteType.APPROVE_WITH_CHANGES,
        "질문차단": VoteType.BLOCKED_BY_QUESTION,
        "거부": VoteType.REJECT,
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_vote(self, text: str) -> VoteType:
        """Extract the vote from an agent response.

        Returns APPROVE_WITH_CHANGES as default when no explicit vote is found.
        """
        match = self.VOTE_PATTERN.search(text)
        if match is None:
            return VoteType.APPROVE_WITH_CHANGES
        return self.VOTE_ALIASES[match.group(1).upper()]

    def evaluate_structured(
        self, opinions: dict[str, str]
    ) -> StructuredConsensusResult:
        """Evaluate structured votes from all agents.

        Args:
            opinions: mapping of agent name to its opinion/response text.

        Returns:
            StructuredConsensusResult with vote tallies, blockers, and
            open questions.
        """
        from trinity.models import Blueprint  # noqa: F401 — reserved for future use

        votes: dict[str, VoteType] = {}
        vote_count: dict[str, int] = {}
        blockers: list[str] = []
        open_questions: list[OpenQuestion] = []

        for agent, text in opinions.items():
            vote = self.extract_vote(text)
            votes[agent] = vote
            key = vote.value
            vote_count[key] = vote_count.get(key, 0) + 1

            if vote == VoteType.REJECT:
                blockers.append(f"{agent}: rejected the design")

            if vote == VoteType.BLOCKED_BY_QUESTION:
                question_text = self._extract_question_text(text)
                open_questions.append(
                    OpenQuestion(
                        id=f"q-{agent}",
                        question=question_text,
                        raised_by=[agent],
                    )
                )

        total = len(opinions)
        if total == 0:
            return StructuredConsensusResult(
                reached=False,
                vote_count=vote_count,
                final_blueprint=None,
                open_questions=open_questions,
                blockers=blockers,
            )

        positive = vote_count.get("approve", 0) + vote_count.get(
            "approve_with_changes", 0
        )

        # Single-agent shortcut
        if total == 1:
            single_vote = list(votes.values())[0]
            reached = single_vote in (VoteType.APPROVE, VoteType.APPROVE_WITH_CHANGES)
        else:
            reached = (
                (positive / total) >= 0.6
                and len(open_questions) == 0
                and len(blockers) == 0
            )

        return StructuredConsensusResult(
            reached=reached,
            vote_count=vote_count,
            final_blueprint=None,
            open_questions=open_questions,
            blockers=blockers,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_question_text(text: str) -> str:
        """Return the lines after the VOTE line as the question text."""
        lines = text.splitlines()
        vote_line_idx: int | None = None
        for i, line in enumerate(lines):
            if StructuredConsensusEngine.VOTE_PATTERN.search(line):
                vote_line_idx = i
                break

        if vote_line_idx is None:
            return ""

        remaining = lines[vote_line_idx + 1 :]
        question = "\n".join(remaining).strip()
        return question if question else "No question text provided"
