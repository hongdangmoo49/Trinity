"""PromptCompressor — heuristic text compression for round opinions.

Reduces old round opinions to concise summaries using extractive
sentence selection based on keyword signals and position scoring.
No LLM calls are made; everything is local heuristic processing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class PromptCompressor:
    """Compresses agent opinions into concise summaries.

    Uses extractive summarization: splits text into sentences,
    scores them by keyword signal presence and position, then
    selects the top-scoring sentences within a token budget.

    Attributes:
        max_summary_tokens: Target maximum token count for compressed output.
    """

    max_summary_tokens: int = 200

    # Signal words that indicate important content — English and Korean
    _KEY_SIGNAL_WORDS: list[str] = field(
        default_factory=lambda: [
            # English
            "recommend",
            "suggest",
            "agree",
            "disagree",
            "should",
            "important",
            "must",
            "critical",
            "propose",
            "conclusion",
            "key",
            "best",
            "worst",
            "advantage",
            "disadvantage",
            "benefit",
            "concern",
            "risk",
            "option",
            "alternatives",
            "prefer",
            "consider",
            "essential",
            "significant",
            # Korean
            "동의",   # agree
            "반대",   # oppose
            "제안",   # propose
            "추천",   # recommend
            "중요",   # important
        ],
        init=False,
        repr=False,
    )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def estimate_tokens(self, text: str) -> int:
        """Return a rough token estimate for *text*.

        Uses ~1.3 tokens per word for English text and ~1.5 tokens
        per character for CJK (Chinese / Japanese / Korean) text.
        """
        if not text:
            return 0

        # Detect CJK proportion
        cjk_pattern = re.compile(
            r"[一-鿿"   # CJK Unified Ideographs
            r"぀-ゟ"    # Hiragana
            r"゠-ヿ"    # Katakana
            r"가-힯"    # Hangul Syllables
            r"]"
        )
        cjk_chars = len(cjk_pattern.findall(text))
        total_chars = len(text)
        cjk_ratio = cjk_chars / total_chars if total_chars else 0.0

        if cjk_ratio > 0.3:
            # Predominantly CJK: ~1.5 tokens per character
            return int(total_chars * 1.5)
        else:
            # Predominantly English/latin: ~1.3 tokens per word
            words = len(text.split())
            return int(words * 1.3)

    def compress_heuristic(self, text: str) -> str:
        """Compress a single text string using heuristic sentence selection.

        Steps:
            1. If text is empty, return "".
            2. If text fits within budget, return as-is.
            3. Split into sentences.
            4. Score each sentence (keyword signals + position bonus).
            5. Select top-scoring sentences within budget, preserving order.
        """
        if not text:
            return ""

        estimated = self.estimate_tokens(text)
        if estimated <= self.max_summary_tokens:
            return text

        sentences = self._split_sentences(text)

        if not sentences:
            return self._truncate_to_budget(text)

        scored = self._score_sentences(sentences)
        selected = self._select_sentences(sentences, scored)

        if not selected:
            return self._truncate_to_budget(sentences[0])

        return " ".join(selected)

    def compress_opinions_heuristic(self, opinions: dict[str, str]) -> str:
        """Compress multiple agent opinions into a formatted summary.

        Divides the token budget evenly across agents, compresses each
        opinion individually, then formats with the agent name.

        Args:
            opinions: Mapping of agent name to their opinion text.

        Returns:
            Formatted string with ``**agent_name**: compressed_opinion``
            lines joined by newlines.  Returns "" for empty input.
        """
        if not opinions:
            return ""

        num_agents = len(opinions)
        per_agent_budget = max(
            self.max_summary_tokens // num_agents,
            20,  # minimum viable budget
        )

        parts: list[str] = []
        for agent_name, opinion in opinions.items():
            sub = PromptCompressor(max_summary_tokens=per_agent_budget)
            compressed = sub.compress_heuristic(opinion)
            parts.append(f"**{agent_name}**: {compressed}")

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences on common terminators."""
        raw = re.split(r"(?<=[.!?])(?:\s+|$)", text.strip())
        return [s.strip() for s in raw if s.strip()]

    def _score_sentences(self, sentences: list[str]) -> list[tuple[int, float]]:
        """Score each sentence and return (index, score) pairs.

        Scoring:
            - +3 for each signal keyword found (case-insensitive)
            - +2 bonus for the first sentence (position bias)
            - +1 for sentences that contain numeric data (data-backed claims)
        """
        scored: list[tuple[int, float]] = []
        for idx, sentence in enumerate(sentences):
            score = 0.0
            lower = sentence.lower()

            for keyword in self._KEY_SIGNAL_WORDS:
                if keyword.lower() in lower:
                    score += 3.0

            if idx == 0:
                score += 2.0

            if re.search(r"\d+%|\d+\s*(percent|percentile)", lower):
                score += 1.0

            scored.append((idx, score))

        return scored

    def _select_sentences(
        self, sentences: list[str], scored: list[tuple[int, float]]
    ) -> list[str]:
        """Select highest-scoring sentences within budget, original order."""
        by_score = sorted(scored, key=lambda x: (-x[1], x[0]))

        selected_indices: list[int] = []
        used_tokens = 0

        for idx, _score in by_score:
            sentence = sentences[idx]
            # Estimate tokens for the sentence plus a separator space
            token_cost = self.estimate_tokens(sentence) + 1
            if used_tokens + token_cost <= self.max_summary_tokens:
                selected_indices.append(idx)
                used_tokens += token_cost
            # Once budget is exhausted, stop trying (remaining are lower score)
            # but we keep iterating since some shorter sentences might still fit

        # Return in original document order
        selected_indices.sort()
        return [sentences[i] for i in selected_indices]

    def _truncate_to_budget(self, text: str) -> str:
        """Truncate text to fit within the token budget, appending '...'."""
        budget = self.max_summary_tokens
        words = text.split()

        # Binary-search style: build candidate and check actual token count
        # to avoid accumulated rounding errors from per-word estimates.
        lo, hi = 0, len(words)
        best: list[str] = []

        while lo <= hi:
            mid = (lo + hi) // 2
            candidate = " ".join(words[:mid])
            if mid < len(words):
                candidate += " ..."
            tokens = self.estimate_tokens(candidate)
            if tokens <= budget:
                best = words[:mid]
                lo = mid + 1
            else:
                hi = mid - 1

        if best and len(best) < len(words):
            best.append("...")

        return " ".join(best) if best else ""
