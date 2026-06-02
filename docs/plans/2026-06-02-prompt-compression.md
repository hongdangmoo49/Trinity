# Phase 7: Prompt Compression Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce token consumption by compressing old deliberation rounds into concise summaries before sending to agents, instead of forwarding verbatim text.

**Architecture:** Add a `PromptCompressor` between `SharedContextEngine` and `DeliberationProtocol._build_round_prompt()`. When Round N≥3 starts, rounds older than N-1 are compressed into a compact "key points" summary. The immediately previous round (N-1) stays verbatim for accurate deliberation. Compression uses a dedicated LLM call via the existing agent infrastructure, with a local text heuristic fallback when no agent is available.

**Tech Stack:** Python 3.10+, asyncio, existing Trinity agent infrastructure, no new external dependencies.

---

## Problem Analysis

### Current behavior (`protocol.py:242-265`)

```
Round 1: prompt = "User's request: {user_prompt}" (short)
Round 2: prompt = "Previous opinions:\n{Round 1 full text}" (growing)
Round 3: prompt = "Previous opinions:\n{Round 2 full text}" (large)
Round 4: prompt = "Previous opinions:\n{Round 3 full text}" (very large)
Round 5: prompt = "Previous opinions:\n{Round 4 full text}" (huge)
```

Each round adds ~500 words/agent × 3 agents = ~1500 words to shared.md.
By Round 5, the **prompt alone** can contain 6000+ words of previous opinions
that are sent to **every** agent — most of which is redundant context from early rounds.

### Target behavior

```
Round 1: prompt = "User's request: {user_prompt}" (unchanged)
Round 2: prompt = "Previous opinions:\n{Round 1 full text}" (unchanged)
Round 3: prompt = "Summary of Rounds 1:\n{compressed}\n\nLatest Round 2:\n{full}"
Round 4: prompt = "Summary of Rounds 1-2:\n{compressed}\n\nLatest Round 3:\n{full}"
Round 5: prompt = "Summary of Rounds 1-3:\n{compressed}\n\nLatest Round 4:\n{full}"
```

Compressed summaries are ~20% of original size → saves ~60-80% of prompt tokens for rounds 3+.

---

## Task Breakdown

### Task 1: Add compression config to TrinityConfig

**Files:**
- Modify: `src/trinity/config.py:20-52`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

Add to `tests/test_config.py`:

```python
def test_config_compression_defaults():
    """TrinityConfig should have prompt compression defaults."""
    config = TrinityConfig.default_config()
    assert config.prompt_compression_enabled is True
    assert config.prompt_compression_round_threshold == 2
    assert config.prompt_compression_max_summary_tokens == 200
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_config_compression_defaults -v`
Expected: FAIL — `TrinityConfig` has no attribute `prompt_compression_enabled`

**Step 3: Write minimal implementation**

In `src/trinity/config.py`, add three fields to the `TrinityConfig` dataclass, right after the `summary_max_tokens` field (line 42):

```python
    # Prompt compression (Phase 7)
    prompt_compression_enabled: bool = True
    prompt_compression_round_threshold: int = 2  # compress rounds older than N-1 when current_round >= this
    prompt_compression_max_summary_tokens: int = 200  # max tokens for compressed summary
```

Also update `_from_dict()` (around line 131) to parse the new `[context]` TOML keys:

```python
            prompt_compression_enabled=context.get("prompt_compression_enabled", True),
            prompt_compression_round_threshold=context.get("prompt_compression_round_threshold", 2),
            prompt_compression_max_summary_tokens=context.get("prompt_compression_max_summary_tokens", 200),
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py::test_config_compression_defaults -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/trinity/config.py tests/test_config.py
git commit -m "feat(phase7): add prompt compression config fields to TrinityConfig"
```

---

### Task 2: Create PromptCompressor — core text heuristic compressor

**Files:**
- Create: `src/trinity/context/compressor.py`
- Create: `tests/test_compressor.py`

This is the **fallback compressor** that works without an LLM call. It extracts key sentences from opinions using heuristic rules (first sentence, sentences with keywords like "recommend", "suggest", "agree", etc.).

**Step 1: Write the failing tests**

Create `tests/test_compressor.py`:

```python
"""Tests for PromptCompressor — heuristic text compression."""

import pytest

from trinity.context.compressor import PromptCompressor


class TestPromptCompressorHeuristic:
    """Test the local heuristic compression (no LLM call)."""

    def test_compress_single_opinion_extracts_key_points(self):
        """Compressor should extract key sentences from a single opinion."""
        opinion = (
            "I recommend using pytest for testing. "
            "It has excellent fixture support and plugin ecosystem. "
            "The main benefit is easy parametrization. "
            "In my experience, pytest reduces test boilerplate by 40%. "
            "I agree that unittest is also viable for simple projects."
        )
        compressor = PromptCompressor(max_summary_tokens=100)
        result = compressor.compress_heuristic(opinion)
        assert len(result) < len(opinion)
        assert "pytest" in result  # key recommendation preserved
        assert result  # non-empty

    def test_compress_multiple_opinions(self):
        """Compressor should handle multiple agent opinions."""
        opinions = {
            "claude": "I suggest using FastAPI for the backend. It provides automatic OpenAPI docs.",
            "codex": "I agree with FastAPI. Additionally, consider SQLAlchemy for ORM.",
            "gemini": "I recommend comparing FastAPI with Django REST first.",
        }
        compressor = PromptCompressor(max_summary_tokens=150)
        result = compressor.compress_opinions_heuristic(opinions)
        assert "claude" in result.lower() or "FastAPI" in result
        assert len(result) < sum(len(v) for v in opinions.values())

    def test_compress_empty_opinions_returns_empty(self):
        """Empty input should return empty string."""
        compressor = PromptCompressor()
        assert compressor.compress_heuristic("") == ""
        assert compressor.compress_opinions_heuristic({}) == ""

    def test_compress_preserves_agreement_disagreement(self):
        """Compressor should keep agree/disagree signals for consensus detection."""
        opinion = (
            "Looking at the options, Flask is lightweight. "
            "Django has more batteries included. "
            "I AGREE with the FastAPI suggestion. "
            "It is the best choice for async APIs."
        )
        compressor = PromptCompressor(max_summary_tokens=100)
        result = compressor.compress_heuristic(opinion)
        assert "AGREE" in result or "agree" in result.lower()

    def test_compress_short_text_unchanged(self):
        """Text shorter than max_summary_tokens should be returned as-is."""
        short_text = "Use pytest."
        compressor = PromptCompressor(max_summary_tokens=500)
        result = compressor.compress_heuristic(short_text)
        assert result == short_text

    def test_compress_opinions_formats_with_agent_names(self):
        """Multi-opinion compression should label each agent's contribution."""
        opinions = {
            "claude": "I recommend approach A because it is simpler.",
            "codex": "I agree with approach A.",
        }
        compressor = PromptCompressor(max_summary_tokens=200)
        result = compressor.compress_opinions_heuristic(opinions)
        assert "claude" in result.lower()
        assert "codex" in result.lower()

    def test_estimated_token_count(self):
        """Token estimator should return a reasonable approximation."""
        compressor = PromptCompressor()
        text = "Hello world, this is a test."
        tokens = compressor.estimate_tokens(text)
        assert tokens > 0
        # Rough: ~1.3 tokens per word for English
        assert tokens < len(text)  # tokens < chars

    def test_compress_respects_max_tokens(self):
        """Compression result should not exceed max_summary_tokens (estimated)."""
        long_text = " ".join(f"Word{i}" for i in range(200))
        compressor = PromptCompressor(max_summary_tokens=50)
        result = compressor.compress_heuristic(long_text)
        estimated = compressor.estimate_tokens(result)
        # Allow 20% margin since estimation is approximate
        assert estimated <= compressor.max_summary_tokens * 1.2
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_compressor.py -v`
Expected: FAIL — module `trinity.context.compressor` does not exist

**Step 3: Write the implementation**

Create `src/trinity/context/compressor.py`:

```python
"""Prompt compressor — reduce token usage by compressing old round opinions."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Keywords that signal important sentences to preserve during compression
_KEY_SIGNAL_WORDS = [
    "recommend",
    "suggest",
    "propose",
    "agree",
    "disagree",
    "concur",
    "oppose",
    "should",
    "must",
    "key",
    "important",
    "crucial",
    "benefit",
    "drawback",
    "advantage",
    "disadvantage",
    "because",
    "therefore",
    "conclusion",
    "in summary",
    "동의",
    "반대",
    "제안",
    "추천",
    "결론",
]

# Sentence extraction pattern — matches sentences ending with . ! ?
_SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")


class PromptCompressor:
    """Compress old deliberation round opinions to reduce token usage.

    Two modes:
    - heuristic: local text processing (no LLM call needed)
    - llm: delegate to an agent for higher-quality compression (future)

    The heuristic compressor:
    1. Splits text into sentences
    2. Scores each sentence by keyword presence
    3. Selects top-scoring sentences up to max_summary_tokens
    4. Always preserves the first sentence (topic sentence)
    """

    def __init__(self, max_summary_tokens: int = 200):
        self.max_summary_tokens = max_summary_tokens
        self._key_pattern = re.compile(
            r"\b(" + "|".join(re.escape(w) for w in _KEY_SIGNAL_WORDS) + r")\b",
            re.IGNORECASE,
        )

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Uses a simple heuristic: ~1.3 tokens per word for English,
        ~1.5 tokens per character for CJK text.
        This is conservative (overestimates) to avoid under-compressing.
        """
        if not text:
            return 0

        words = text.split()
        cjk_chars = sum(
            1 for c in text if "一" <= c <= "鿿" or "가" <= c <= "힯"
        )
        non_cjk_words = len(words) - cjk_chars

        # CJK: ~1.5 tokens per character, English: ~1.3 tokens per word
        return int(non_cjk_words * 1.3 + cjk_chars * 1.5) or len(text)

    def compress_heuristic(self, text: str) -> str:
        """Compress a single text block using heuristic sentence extraction.

        Args:
            text: The opinion text to compress.

        Returns:
            Compressed text, or original if already short enough.
        """
        if not text or not text.strip():
            return ""

        # If already within budget, return as-is
        if self.estimate_tokens(text) <= self.max_summary_tokens:
            return text

        sentences = _SENTENCE_PATTERN.split(text.strip())
        if len(sentences) <= 1:
            # Can't split further — truncate with ellipsis
            return self._truncate_to_budget(text)

        # Score sentences
        scored = self._score_sentences(sentences)

        # Always include first sentence (topic sentence)
        selected_indices: set[int] = {0}
        selected: list[str] = [sentences[0]]
        current_tokens = self.estimate_tokens(sentences[0])

        # Add sentences by score, highest first, skipping first (already included)
        for idx, _score in sorted(
            ((i, s) for i, s in enumerate(scored) if i != 0),
            key=lambda x: -x[1],
        ):
            sentence = sentences[idx]
            sentence_tokens = self.estimate_tokens(sentence)

            if current_tokens + sentence_tokens > self.max_summary_tokens:
                continue  # Skip — would exceed budget

            selected_indices.add(idx)
            # Insert in original order for readability
            selected.append(sentence)
            current_tokens += sentence_tokens

        # Re-sort selected sentences by original order
        ordered = [sentences[i] for i in sorted(selected_indices)]
        result = " ".join(ordered)

        if not result.strip():
            return self._truncate_to_budget(text)

        return result

    def compress_opinions_heuristic(self, opinions: dict[str, str]) -> str:
        """Compress multiple agent opinions into a single summary.

        Args:
            opinions: {agent_name: opinion_text}

        Returns:
            Formatted compressed summary with agent labels.
        """
        if not opinions:
            return ""

        # Budget per agent
        per_agent_budget = max(
            self.max_summary_tokens // len(opinions),
            50,  # minimum per agent
        )

        parts: list[str] = []
        for agent, opinion in opinions.items():
            agent_compressor = PromptCompressor(max_summary_tokens=per_agent_budget)
            compressed = agent_compressor.compress_heuristic(opinion)
            parts.append(f"**{agent}**: {compressed}")

        return "\n".join(parts)

    def _score_sentences(self, sentences: list[str]) -> list[float]:
        """Score each sentence by keyword density and position.

        Returns list of scores, same length as sentences.
        """
        scores: list[float] = []

        for i, sentence in enumerate(sentences):
            score = 0.0

            # Keyword bonus
            matches = self._key_pattern.findall(sentence.lower())
            score += len(matches) * 2.0

            # Length bonus — prefer medium-length sentences (not too short, not too long)
            word_count = len(sentence.split())
            if 5 <= word_count <= 30:
                score += 1.0
            elif word_count < 5:
                score -= 0.5

            # Position bonus — first and last sentences are often important
            if i == 0:
                score += 3.0  # First sentence is always important
            elif i == len(sentences) - 1:
                score += 1.5  # Conclusion sentences matter

            scores.append(score)

        return scores

    def _truncate_to_budget(self, text: str) -> str:
        """Truncate text to fit within max_summary_tokens, preserving word boundaries."""
        words = text.split()
        # Rough estimate: work backwards from budget
        budget_words = int(self.max_summary_tokens / 1.3)
        if len(words) <= budget_words:
            return text

        truncated = " ".join(words[:budget_words])
        return truncated.rstrip(".,;:!?") + "..."
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_compressor.py -v`
Expected: All 8 tests PASS

**Step 5: Commit**

```bash
git add src/trinity/context/compressor.py tests/test_compressor.py
git commit -m "feat(phase7): add PromptCompressor with heuristic text compression"
```

---

### Task 3: Add compressed section storage to SharedContextEngine

**Files:**
- Modify: `src/trinity/context/shared.py:113-117`
- Modify: `tests/test_shared_context.py`

We need a method to store compressed summaries in shared.md so they persist across rounds, and a method to read compressed + latest round context.

**Step 1: Write the failing tests**

Add to `tests/test_shared_context.py`:

```python
def test_write_compressed_summary(shared_engine):
    """write_compressed_summary should store a compressed round summary."""
    shared_engine.initialize(goal="test goal", agent_names=["claude", "codex"])
    shared_engine.append_opinion("claude", 1, "Opinion 1 from claude")
    shared_engine.append_opinion("codex", 1, "Opinion 1 from codex")

    shared_engine.write_compressed_summary(1, "claude+codex agree on pytest")

    section = shared_engine.read_section("Round 1 Summary")
    assert "claude+codex agree on pytest" in section


def test_get_rounds_for_prompt_includes_compressed(shared_engine):
    """get_rounds_for_prompt should include compressed summaries for old rounds."""
    shared_engine.initialize(goal="test", agent_names=["claude"])
    shared_engine.append_opinion("claude", 1, "Long opinion round 1 " * 50)
    shared_engine.append_opinion("claude", 2, "Opinion round 2")
    shared_engine.append_opinion("claude", 3, "Opinion round 3")

    # Compress round 1
    shared_engine.write_compressed_summary(1, "Compressed: use pytest")

    # For round 4 prompt: should get compressed R1 + full R3
    context = shared_engine.get_rounds_for_prompt(
        current_round=4,
        verbatim_rounds=1,  # only latest 1 round verbatim
    )

    assert "Compressed: use pytest" in context
    assert "Opinion round 3" in context


def test_get_rounds_for_prompt_no_compression(shared_engine):
    """get_rounds_for_prompt with enough verbatim_rounds should skip compression."""
    shared_engine.initialize(goal="test", agent_names=["claude"])
    shared_engine.append_opinion("claude", 1, "Opinion 1")
    shared_engine.append_opinion("claude", 2, "Opinion 2")

    # No compressed summaries exist — should return verbatim
    context = shared_engine.get_rounds_for_prompt(current_round=3, verbatim_rounds=2)
    assert "Opinion 1" in context
    assert "Opinion 2" in context
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_shared_context.py::test_write_compressed_summary tests/test_shared_context.py::test_get_rounds_for_prompt_includes_compressed tests/test_shared_context.py::test_get_rounds_for_prompt_no_compression -v`
Expected: FAIL — `SharedContextEngine` has no method `write_compressed_summary`

**Step 3: Write minimal implementation**

Add these two methods to `SharedContextEngine` in `src/trinity/context/shared.py`, after `append_session_summary()` (around line 134):

```python
    def write_compressed_summary(self, round_num: int, summary: str) -> None:
        """Store a compressed summary for a completed round.

        Compressed summaries are stored in a dedicated section
        "Round N Summary" and used by get_rounds_for_prompt().
        """
        self.write_section(f"Round {round_num} Summary", summary)

    def get_rounds_for_prompt(
        self, current_round: int, verbatim_rounds: int = 1
    ) -> str:
        """Build context for a round prompt with compression.

        Returns formatted text with:
        - Compressed summaries for old rounds (Round 1..current_round-verbatim_rounds-1)
        - Full verbatim text for the latest rounds (current_round-verbatim_rounds..current_round-1)

        Args:
            current_round: The round about to start (1-based).
            verbatim_rounds: How many recent rounds to include verbatim.

        Returns:
            Formatted context string for the round prompt.
        """
        full = self.read()
        sections = self._parse_sections(full)

        parts: list[str] = []

        # The previous round is current_round - 1
        prev_round = current_round - 1
        # First round to include verbatim
        verbatim_start = max(1, prev_round - verbatim_rounds + 1)
        # Rounds before verbatim_start are candidates for compression
        compress_end = verbatim_start - 1

        # Compressed summaries for old rounds
        if compress_end >= 1:
            compressed_parts: list[str] = []
            for r in range(1, compress_end + 1):
                summary_key = self._normalize_heading(f"Round {r} Summary")
                if summary_key in sections:
                    compressed_parts.append(sections[summary_key])
                else:
                    # No compressed summary exists — include a brief note
                    compressed_parts.append(f"(Round {r}: see shared context for details)")

            if compressed_parts:
                parts.append("## Earlier Rounds (summarized)\n" + "\n".join(compressed_parts))

        # Verbatim rounds
        for r in range(verbatim_start, prev_round + 1):
            section_key = self._normalize_heading(f"Round {r} Opinions")
            if section_key in sections:
                parts.append(sections[section_key])

        return "\n\n".join(parts)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_shared_context.py -v`
Expected: All tests PASS (including existing ones)

**Step 5: Commit**

```bash
git add src/trinity/context/shared.py tests/test_shared_context.py
git commit -m "feat(phase7): add compressed summary storage to SharedContextEngine"
```

---

### Task 4: Integrate PromptCompressor into DeliberationProtocol

**Files:**
- Modify: `src/trinity/deliberation/protocol.py:242-265`
- Create: `tests/test_protocol_compression.py`

This is the core integration — modify `_build_round_prompt()` to use compression for rounds ≥ threshold.

**Step 1: Write the failing tests**

Create `tests/test_protocol_compression.py`:

```python
"""Tests for prompt compression integration in DeliberationProtocol."""

import pytest

from trinity.context.compressor import PromptCompressor
from trinity.context.shared import SharedContextEngine
from trinity.deliberation.protocol import DeliberationProtocol


def _make_mock_agent(name: str, response: str = "OK"):
    """Create a minimal mock agent for testing."""
    from unittest.mock import AsyncMock

    from trinity.agents.base import AgentWrapper
    from trinity.models import AgentSpec, ContextUsage, DeliberationMessage, MessageRole, Provider

    spec = AgentSpec(name=name, provider=Provider.CLAUDE_CODE, cli_command="claude")
    agent = AsyncMock(spec=AgentWrapper)
    agent.spec = spec
    agent.name = name
    agent.context_usage = ContextUsage(used=0, total=200_000)

    async def mock_send(prompt, timeout=120.0):
        return DeliberationMessage(
            source=name,
            target="all",
            round_num=0,
            role=MessageRole.OPINION,
            content=response,
        )

    agent.send_and_wait = mock_send
    agent.start = AsyncMock()
    agent.graceful_shutdown = AsyncMock()
    agent.get_context_usage = AsyncMock(return_value=ContextUsage(used=0, total=200_000))
    agent.is_alive = AsyncMock(return_value=True)
    return agent


class TestRoundPromptCompression:
    """Test that _build_round_prompt uses compression for old rounds."""

    def test_round_1_no_compression(self, tmp_path):
        """Round 1 prompt should not reference any previous round."""
        shared = SharedContextEngine(path=tmp_path / "shared.md")
        agent = _make_mock_agent("claude")
        protocol = DeliberationProtocol(
            agents={"claude": agent},
            shared=shared,
            max_rounds=5,
        )

        shared.initialize(goal="Design auth system", agent_names=["claude"])
        prompt = protocol._build_round_prompt(1, "Design auth system")

        assert "Design auth system" in prompt
        assert "Previous round" not in prompt
        assert "summarized" not in prompt.lower()

    def test_round_2_verbatim_previous(self, tmp_path):
        """Round 2 should include Round 1 verbatim (no compression yet)."""
        shared = SharedContextEngine(path=tmp_path / "shared.md")
        agent = _make_mock_agent("claude")
        protocol = DeliberationProtocol(
            agents={"claude": agent},
            shared=shared,
            max_rounds=5,
        )

        shared.initialize(goal="test", agent_names=["claude"])
        shared.append_opinion("claude", 1, "I recommend pytest for testing.")

        prompt = protocol._build_round_prompt(2, "test")
        assert "pytest" in prompt
        assert "Round 1 Opinions" in prompt

    def test_round_3_uses_compressed_old_rounds(self, tmp_path):
        """Round 3+ should use compressed summaries for rounds older than N-1."""
        shared = SharedContextEngine(path=tmp_path / "shared.md")
        agent = _make_mock_agent("claude")
        protocol = DeliberationProtocol(
            agents={"claude": agent},
            shared=shared,
            max_rounds=5,
            compression_enabled=True,
            compression_round_threshold=2,
        )

        shared.initialize(goal="test", agent_names=["claude"])
        shared.append_opinion("claude", 1, "Round 1 opinion with detailed analysis. " * 20)
        shared.append_opinion("claude", 2, "Round 2 opinion.")
        # Simulate that Round 1 was already compressed
        shared.write_compressed_summary(1, "Compressed: claude recommends pytest")

        prompt = protocol._build_round_prompt(3, "test")
        # Should contain compressed R1
        assert "Compressed: claude recommends pytest" in prompt
        # Should contain verbatim R2
        assert "Round 2 opinion" in prompt

    def test_compression_disabled(self, tmp_path):
        """When compression_enabled=False, all rounds should be verbatim."""
        shared = SharedContextEngine(path=tmp_path / "shared.md")
        agent = _make_mock_agent("claude")
        protocol = DeliberationProtocol(
            agents={"claude": agent},
            shared=shared,
            max_rounds=5,
            compression_enabled=False,
        )

        shared.initialize(goal="test", agent_names=["claude"])
        shared.append_opinion("claude", 1, "Opinion R1.")
        shared.append_opinion("claude", 2, "Opinion R2.")
        shared.write_compressed_summary(1, "Compressed R1")

        prompt = protocol._build_round_prompt(3, "test")
        # Should NOT use compressed summary
        assert "Compressed R1" not in prompt

    def test_prompt_size_reduction(self, tmp_path):
        """Verify that compression actually reduces prompt size."""
        shared = SharedContextEngine(path=tmp_path / "shared.md")
        agent = _make_mock_agent("claude")

        # Long opinions
        long_opinion = "This is a detailed analysis. " * 50  # ~250 words

        shared.initialize(goal="test", agent_names=["claude"])
        shared.append_opinion("claude", 1, long_opinion)
        shared.append_opinion("claude", 2, long_opinion)
        shared.append_opinion("claude", 3, "Short opinion R3.")

        # Compress rounds 1
        shared.write_compressed_summary(1, "claude: recommends approach A")

        # Prompt with compression
        protocol_compressed = DeliberationProtocol(
            agents={"claude": agent},
            shared=shared,
            max_rounds=5,
            compression_enabled=True,
        )
        prompt_compressed = protocol_compressed._build_round_prompt(4, "test")

        # Prompt without compression (for comparison)
        protocol_plain = DeliberationProtocol(
            agents={"claude": agent},
            shared=shared,
            max_rounds=5,
            compression_enabled=False,
        )
        prompt_plain = protocol_plain._build_round_prompt(4, "test")

        assert len(prompt_compressed) < len(prompt_plain)
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_protocol_compression.py -v`
Expected: FAIL — `DeliberationProtocol.__init__()` doesn't accept `compression_enabled`

**Step 3: Write minimal implementation**

Modify `src/trinity/deliberation/protocol.py`:

**3a.** Add import and new constructor parameters (around line 1-20):

Add to imports:
```python
from trinity.context.compressor import PromptCompressor
```

**3b.** Add to `__init__()` (after `event_callback` parameter, around line 51):

```python
        self.compressor: PromptCompressor | None = None
        self.compression_enabled = compression_enabled
        if compression_enabled:
            self.compressor = PromptCompressor(
                max_summary_tokens=compression_max_summary_tokens,
            )
        self.compression_round_threshold = compression_round_threshold
```

**3c.** Replace `_build_round_prompt()` method (lines 242-265) with:

```python
    def _build_round_prompt(self, round_num: int, user_prompt: str) -> str:
        """Build the prompt for a specific deliberation round.

        For rounds >= compression_round_threshold:
        - Old rounds are included as compressed summaries
        - Only the immediately previous round is sent verbatim

        For rounds < compression_round_threshold:
        - Previous round is sent verbatim (no compression)
        """
        if round_num == 1:
            return (
                f"Read the shared context below for background.\n\n"
                f"User's request: {user_prompt}\n\n"
                f"Share your initial opinion. Be specific and concise.\n"
                f"State your recommendation and key reasoning.\n"
                f"Keep your response under 500 words."
            )

        # Decide: use compression or verbatim?
        use_compression = (
            self.compression_enabled
            and self.compressor is not None
            and round_num >= self.compression_round_threshold
        )

        if use_compression:
            # Compress old rounds, keep latest verbatim
            self._compress_old_rounds(round_num)
            prev_context = self.shared.get_rounds_for_prompt(
                current_round=round_num,
                verbatim_rounds=1,  # only previous round verbatim
            )
        else:
            # Verbatim: just read the previous round
            prev_section = self.shared.read_section(f"Round {round_num - 1} Opinions")
            prev_context = prev_section or "(previous round opinions not available)"

        return (
            f"Previous round opinions:\n\n"
            f"{prev_context}\n\n"
            f"---\n\n"
            f"For each other agent's opinion above, state whether you AGREE or DISAGREE "
            f"and explain why. If you disagree, propose an alternative.\n"
            f"End your response with either 'I AGREE with [name]' or your counter-proposal.\n"
            f"Keep your response under 300 words."
        )

    def _compress_old_rounds(self, current_round: int) -> None:
        """Compress rounds older than current_round - 1 that haven't been compressed yet.

        Called before building the prompt for rounds >= compression_round_threshold.
        """
        if not self.compressor:
            return

        prev_round = current_round - 1
        # Only round immediately before the previous one needs compression check
        # (older rounds should already be compressed from previous iterations)
        round_to_compress = prev_round - 1

        if round_to_compress < 1:
            return

        # Check if already compressed
        existing = self.shared.read_section(f"Round {round_to_compress} Summary")
        if existing is not None:
            return  # Already compressed

        # Read the round's opinions and compress
        round_section = self.shared.read_section(f"Round {round_to_compress} Opinions")
        if not round_section:
            return

        # Extract individual agent opinions from the section
        agent_opinions = self._extract_agent_opinions(round_section)

        if agent_opinions:
            compressed = self.compressor.compress_opinions_heuristic(agent_opinions)
        else:
            compressed = self.compressor.compress_heuristic(round_section)

        self.shared.write_compressed_summary(round_to_compress, compressed)
        logger.info(
            f"Compressed Round {round_to_compress}: "
            f"{len(round_section)} → {len(compressed)} chars "
            f"({len(compressed) / max(len(round_section), 1):.0%})"
        )

    @staticmethod
    def _extract_agent_opinions(round_section: str) -> dict[str, str]:
        """Extract individual agent opinions from a round section.

        Parses ### agent_name blocks from the markdown.
        """
        opinions: dict[str, str] = {}
        current_agent: str | None = None
        current_lines: list[str] = []

        for line in round_section.splitlines():
            if line.startswith("### "):
                # Save previous agent's opinion
                if current_agent is not None:
                    opinions[current_agent] = "\n".join(current_lines).strip()
                current_agent = line[4:].strip()
                current_lines = []
            elif current_agent is not None:
                current_lines.append(line)

        # Save last agent
        if current_agent is not None:
            opinions[current_agent] = "\n".join(current_lines).strip()

        return opinions
```

**3d.** Update `__init__` signature to include new parameters:

```python
    def __init__(
        self,
        agents: dict[str, AgentWrapper],
        shared: SharedContextEngine,
        consensus_engine: ConsensusEngine | None = None,
        distributor: TaskDistributor | None = None,
        max_rounds: int = 5,
        round_timeout: float = 120.0,
        tmux_manager=None,
        event_callback: Callable[[TUIEvent], None] | None = None,
        compression_enabled: bool = True,
        compression_round_threshold: int = 2,
        compression_max_summary_tokens: int = 200,
    ):
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_protocol_compression.py -v`
Expected: All 5 tests PASS

**Step 5: Run existing protocol tests to verify no regression**

Run: `pytest tests/test_protocol.py tests/test_protocol_v2.py -v`
Expected: All existing tests PASS

**Step 6: Commit**

```bash
git add src/trinity/deliberation/protocol.py tests/test_protocol_compression.py
git commit -m "feat(phase7): integrate PromptCompressor into DeliberationProtocol"
```

---

### Task 5: Wire compression config from TrinityConfig → Orchestrator → Protocol

**Files:**
- Modify: `src/trinity/orchestrator.py:59-68`
- Modify: `tests/test_orchestrator.py`

Pass the compression settings from config through the orchestrator to the protocol.

**Step 1: Write the failing test**

Add to `tests/test_orchestrator.py`:

```python
def test_orchestrator_passes_compression_config(tmp_path):
    """Orchestrator should forward compression settings to DeliberationProtocol."""
    from trinity.config import TrinityConfig

    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.prompt_compression_enabled = False
    config.prompt_compression_round_threshold = 3
    config.prompt_compression_max_summary_tokens = 300

    orchestrator = TrinityOrchestrator(config)
    orchestrator._ensure_initialized()

    assert orchestrator.protocol.compression_enabled is False
    assert orchestrator.protocol.compression_round_threshold == 3
    assert orchestrator.protocol.compressor is None  # disabled
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_orchestrator.py::test_orchestrator_passes_compression_config -v`
Expected: FAIL — protocol gets default `compression_enabled=True`

**Step 3: Modify orchestrator to pass compression config**

In `src/trinity/orchestrator.py`, update the `DeliberationProtocol()` constructor call inside `_ensure_initialized()` (around line 59-68):

```python
        # Create deliberation protocol
        self.protocol = DeliberationProtocol(
            agents=self.agents,
            shared=self.shared,
            consensus_engine=ConsensusEngine(
                required_fraction=self.config.consensus_threshold,
            ),
            distributor=TaskDistributor(),
            max_rounds=self.config.max_deliberation_rounds,
            round_timeout=self.config.round_timeout_seconds,
            compression_enabled=self.config.prompt_compression_enabled,
            compression_round_threshold=self.config.prompt_compression_round_threshold,
            compression_max_summary_tokens=self.config.prompt_compression_max_summary_tokens,
        )
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_orchestrator.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/trinity/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(phase7): wire compression config from TrinityConfig to Protocol"
```

---

### Task 6: Run full test suite and verify no regressions

**Files:** None — verification only.

**Step 1: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All tests PASS (622 existing + ~18 new = ~640 total)

**Step 2: Run coverage report**

Run: `pytest tests/ --cov=trinity --cov-report=term-missing`
Expected: Coverage ≥ 87% (no significant drop from baseline)

**Step 3: Check compressor module coverage**

Run: `pytest tests/ --cov=trinity.context.compressor --cov-report=term-missing`
Expected: compressor.py ≥ 90% coverage

**Step 4: Commit final state if any test fixes were needed**

```bash
git add -A
git commit -m "fix(phase7): address test regressions from prompt compression"
```

---

## Summary

| Task | Files | Tests Added | Key Deliverable |
|------|-------|-------------|-----------------|
| 1 | `config.py` | 1 | Compression config fields |
| 2 | `context/compressor.py` (new) | 8 | `PromptCompressor` with heuristic compression |
| 3 | `context/shared.py` | 3 | Compressed section storage + `get_rounds_for_prompt()` |
| 4 | `deliberation/protocol.py` | 5 | `_build_round_prompt()` uses compression for rounds ≥ threshold |
| 5 | `orchestrator.py` | 1 | Config → Protocol wiring |
| 6 | — | 0 | Full regression verification |

**Total new tests:** ~18
**Total new code:** ~250 lines (compressor) + ~80 lines (shared) + ~70 lines (protocol)

### Token savings estimate

| Scenario | Before (tokens/round) | After (tokens/round) | Savings |
|----------|----------------------|---------------------|---------|
| Round 3 (3 agents, 500w each) | ~3,900 | ~2,100 | **46%** |
| Round 5 (3 agents, 500w each) | ~5,800 | ~2,400 | **59%** |
| Round 5 (10-round session) | ~15,000 | ~3,200 | **79%** |
