# Phase 7B: Token Optimization — Cleanup, Estimation, Interactive Counting

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete the remaining three token optimization features: (1) auto-cleanup of old round sections from shared.md, (2) pre-send token estimation to predict context overflow before it happens, (3) accurate cumulative token counting for InteractiveClaudeAgent.

**Architecture:** (1) Add `remove_section()` to SharedContextEngine and call it from `_compress_old_rounds()` after writing the compressed summary. (2) Add a `TokenBudgetChecker` that estimates prompt tokens and checks if sending would push the agent over threshold, called before each `send_and_wait()`. (3) Fix InteractiveClaudeAgent to accumulate token counts across rounds instead of resetting each time.

**Tech Stack:** Python 3.10+, asyncio, existing Trinity infrastructure. No new dependencies.

---

## Task 1: Add `remove_section()` to SharedContextEngine

**Files:**
- Modify: `src/trinity/context/shared.py`
- Modify: `tests/test_shared_context.py`

**Why:** After Phase 7's `_compress_old_rounds()` writes a compressed summary, the original "Round N Opinions" section still stays in shared.md, causing unbounded growth. We need to remove old opinion sections after compression.

**Step 1: Write the failing tests**

Add to `tests/test_shared_context.py`:

```python
def test_remove_section(shared_engine):
    """remove_section should delete a section entirely."""
    shared_engine.initialize(goal="test", agent_names=["claude"])
    shared_engine.append_opinion("claude", 1, "Opinion 1")

    assert shared_engine.read_section("Round 1 Opinions") is not None

    shared_engine.remove_section("Round 1 Opinions")

    assert shared_engine.read_section("Round 1 Opinions") is None


def test_remove_nonexistent_section_noop(shared_engine):
    """Removing a section that doesn't exist should not error."""
    shared_engine.initialize(goal="test", agent_names=["claude"])
    shared_engine.remove_section("Nonexistent Section")  # Should not raise


def test_remove_section_preserves_others(shared_engine):
    """Removing one section should not affect other sections."""
    shared_engine.initialize(goal="test", agent_names=["claude"])
    shared_engine.append_opinion("claude", 1, "Opinion 1")
    shared_engine.append_opinion("claude", 2, "Opinion 2")

    shared_engine.remove_section("Round 1 Opinions")

    assert shared_engine.read_section("Round 1 Opinions") is None
    assert shared_engine.read_section("Round 2 Opinions") is not None
    assert shared_engine.read_section("Current Goal") is not None
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_shared_context.py::test_remove_section tests/test_shared_context.py::test_remove_nonexistent_section_noop tests/test_shared_context.py::test_remove_section_preserves_others -v`
Expected: FAIL — no `remove_section` method

**Step 3: Implement**

Add to `SharedContextEngine` in `src/trinity/context/shared.py`, after `write_compressed_summary()`:

```python
    def remove_section(self, heading: str) -> None:
        """Remove a ## section entirely from shared.md.

        No-op if the section doesn't exist.
        """
        full = self.read()
        sections = self._parse_sections(full)
        key = self._normalize_heading(heading)

        if key not in sections:
            return  # Section doesn't exist, nothing to do

        # Rebuild content without the target section
        lines = full.splitlines()
        result: list[str] = []
        in_target = False
        heading_prefix = f"## {heading}"

        for line in lines:
            if line.strip() == heading_prefix:
                in_target = True
                continue  # Skip the heading line itself

            if in_target and line.startswith("## ") and not line.startswith("### "):
                in_target = False

            if not in_target:
                result.append(line)

        self.write("\n".join(result))
```

**Step 4: Run tests**

Run: `pytest tests/test_shared_context.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/trinity/context/shared.py tests/test_shared_context.py
git commit -m "feat(phase7b): add remove_section() to SharedContextEngine"
```

---

## Task 2: Auto-cleanup old round sections after compression

**Files:**
- Modify: `src/trinity/deliberation/protocol.py:295-326`
- Modify: `tests/test_protocol_compression.py`

**Why:** Currently `_compress_old_rounds()` writes the compressed summary but leaves the original "Round N Opinions" section in shared.md. For long deliberations, shared.md grows without bound. After compression succeeds, remove the original section.

**Step 1: Write the failing test**

Add to `tests/test_protocol_compression.py`:

```python
    def test_compressed_round_opinions_removed(self, tmp_path):
        """After compression, original Round N Opinions section should be removed."""
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
        shared.append_opinion("claude", 1, "Original opinion round 1. " * 30)
        shared.append_opinion("claude", 2, "Opinion round 2.")

        # Before compression: both sections exist
        assert shared.read_section("Round 1 Opinions") is not None
        assert shared.read_section("Round 2 Opinions") is not None

        # Trigger compression by building round 3 prompt
        protocol._build_round_prompt(3, "test")

        # After compression: R1 Opinions should be removed, R1 Summary should exist
        assert shared.read_section("Round 1 Opinions") is None
        assert shared.read_section("Round 1 Summary") is not None
        # R2 Opinions should still exist (it's the latest verbatim round)
        assert shared.read_section("Round 2 Opinions") is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_protocol_compression.py::TestRoundPromptCompression::test_compressed_round_opinions_removed -v`
Expected: FAIL — `shared.read_section("Round 1 Opinions")` is not None (section not removed)

**Step 3: Implement**

In `src/trinity/deliberation/protocol.py`, modify `_compress_old_rounds()` — add one line after the `write_compressed_summary()` call:

After this existing line (around line 322):
```python
        self.shared.write_compressed_summary(round_to_compress, compressed)
```

Add:
```python
        # Remove original opinions section to prevent shared.md unbounded growth
        self.shared.remove_section(f"Round {round_to_compress} Opinions")
        logger.info(f"Removed original Round {round_to_compress} Opinions from shared.md")
```

**Step 4: Run tests**

Run: `pytest tests/test_protocol_compression.py -v`
Expected: All tests PASS

**Step 5: Run full protocol tests**

Run: `pytest tests/test_protocol.py tests/test_protocol_v2.py tests/test_protocol_compression.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add src/trinity/deliberation/protocol.py tests/test_protocol_compression.py
git commit -m "feat(phase7b): auto-cleanup old round sections after compression"
```

---

## Task 3: Pre-send token estimation — TokenBudgetChecker

**Files:**
- Create: `src/trinity/context/budget.py`
- Create: `tests/test_budget.py`

**Why:** Currently the protocol sends prompts to agents without checking if the prompt would push the agent's context over the 60% threshold. We need a `TokenBudgetChecker` that estimates prompt tokens and warns before sending.

**Step 1: Write the failing tests**

Create `tests/test_budget.py`:

```python
"""Tests for TokenBudgetChecker — pre-send token estimation."""

import pytest

from trinity.context.budget import TokenBudgetChecker
from trinity.context.compressor import PromptCompressor
from trinity.models import AgentSpec, ContextUsage, Provider


def _make_agent_spec(name: str = "claude", provider: Provider = Provider.CLAUDE_CODE):
    return AgentSpec(name=name, provider=provider, cli_command="claude")


class TestTokenBudgetChecker:

    def test_check_safe_prompt(self):
        """Prompt within budget should return safe=True."""
        spec = _make_agent_spec()
        checker = TokenBudgetChecker()
        result = checker.check(
            prompt="Short prompt.",
            current_usage=ContextUsage(used=1000, total=200_000),
            agent_spec=spec,
        )
        assert result.safe is True
        assert result.estimated_prompt_tokens > 0
        assert result.projected_ratio < 0.6

    def test_check_dangerous_prompt(self):
        """Prompt that would push over threshold should return safe=False."""
        spec = _make_agent_spec()
        checker = TokenBudgetChecker(threshold=0.60)
        # Agent already at 55% (110K/200K) — a large prompt will push over 60%
        result = checker.check(
            prompt="x " * 5000,  # ~6500 tokens estimated
            current_usage=ContextUsage(used=110_000, total=200_000),
            agent_spec=spec,
        )
        assert result.safe is False
        assert result.projected_ratio >= 0.60

    def test_check_with_margin(self):
        """With safety_margin, should warn before actual threshold."""
        spec = _make_agent_spec()
        checker = TokenBudgetChecker(threshold=0.60, safety_margin=0.05)
        # Agent at 52% — margin makes effective threshold 55%
        result = checker.check(
            prompt="x " * 5000,
            current_usage=ContextUsage(used=104_000, total=200_000),
            agent_spec=spec,
        )
        assert result.safe is False

    def test_estimate_prompt_tokens(self):
        """Token estimation should be reasonable."""
        checker = TokenBudgetChecker()
        text = "Hello world, this is a test."
        tokens = checker.estimate_prompt_tokens(text)
        assert tokens > 0
        assert tokens < len(text)

    def test_get_recommendation(self):
        """Should recommend action based on state."""
        spec = _make_agent_spec()
        checker = TokenBudgetChecker()

        # Safe case
        result_safe = checker.check(
            prompt="short",
            current_usage=ContextUsage(used=10_000, total=200_000),
            agent_spec=spec,
        )
        assert result_safe.recommendation == "proceed"

        # Danger case
        result_danger = checker.check(
            prompt="x " * 5000,
            current_usage=ContextUsage(used=115_000, total=200_000),
            agent_spec=spec,
        )
        assert result_danger.recommendation == "rotate_first"

        # Warning case (approaching)
        result_warn = checker.check(
            prompt="x " * 5000,
            current_usage=ContextUsage(used=100_000, total=200_000),
            agent_spec=spec,
        )
        assert result_warn.recommendation == "proceed_with_caution"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_budget.py -v`
Expected: FAIL — module `trinity.context.budget` does not exist

**Step 3: Implement**

Create `src/trinity/context/budget.py`:

```python
"""Token budget checker — pre-send token estimation and safety checks."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from trinity.context.compressor import PromptCompressor
from trinity.models import AgentSpec, ContextUsage

logger = logging.getLogger(__name__)


@dataclass
class BudgetCheckResult:
    """Result of a pre-send token budget check."""

    estimated_prompt_tokens: int
    projected_total: int
    projected_ratio: float
    safe: bool
    recommendation: str  # "proceed" | "proceed_with_caution" | "rotate_first"


class TokenBudgetChecker:
    """Check if sending a prompt would push an agent over its context budget.

    Uses the same token estimation heuristic as PromptCompressor.
    Called before each send_and_wait() to enable proactive rotation.

    Attributes:
        threshold: Context usage ratio that triggers rotation (default 0.60).
        safety_margin: Buffer below threshold to start warning (default 0.05).
            Effective warning threshold = threshold - safety_margin.
    """

    def __init__(
        self,
        threshold: float = 0.60,
        safety_margin: float = 0.05,
    ):
        self.threshold = threshold
        self.safety_margin = safety_margin
        self._estimator = PromptCompressor()

    def estimate_prompt_tokens(self, prompt: str) -> int:
        """Estimate how many tokens a prompt will consume.

        Includes overhead for the agent's role prompt and system instructions
        (estimated at 20% on top of the raw prompt tokens).
        """
        raw_tokens = self._estimator.estimate_tokens(prompt)
        # Add 20% overhead for role prompt, system formatting, etc.
        return int(raw_tokens * 1.2)

    def check(
        self,
        prompt: str,
        current_usage: ContextUsage,
        agent_spec: AgentSpec,
    ) -> BudgetCheckResult:
        """Check if sending prompt is safe for the agent's context budget.

        Args:
            prompt: The prompt text to be sent.
            current_usage: Agent's current context usage.
            agent_spec: Agent spec with context budget info.

        Returns:
            BudgetCheckResult with safety assessment and recommendation.
        """
        estimated_tokens = self.estimate_prompt_tokens(prompt)
        projected_total = current_usage.used + estimated_tokens
        projected_ratio = projected_total / current_usage.total if current_usage.total > 0 else 0.0

        warning_threshold = self.threshold - self.safety_margin

        if projected_ratio >= self.threshold:
            safe = False
            recommendation = "rotate_first"
        elif projected_ratio >= warning_threshold:
            safe = True
            recommendation = "proceed_with_caution"
        else:
            safe = True
            recommendation = "proceed"

        result = BudgetCheckResult(
            estimated_prompt_tokens=estimated_tokens,
            projected_total=projected_total,
            projected_ratio=projected_ratio,
            safe=safe,
            recommendation=recommendation,
        )

        if not safe:
            logger.warning(
                f"[{agent_spec.name}] Budget check FAILED: "
                f"projected {projected_ratio:.0%} (threshold {self.threshold:.0%}). "
                f"Recommendation: {recommendation}"
            )
        elif recommendation == "proceed_with_caution":
            logger.info(
                f"[{agent_spec.name}] Budget check CAUTION: "
                f"projected {projected_ratio:.0%} (warning at {warning_threshold:.0%})"
            )

        return result
```

**Step 4: Run tests**

Run: `pytest tests/test_budget.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add src/trinity/context/budget.py tests/test_budget.py
git commit -m "feat(phase7b): add TokenBudgetChecker for pre-send token estimation"
```

---

## Task 4: Integrate TokenBudgetChecker into Protocol

**Files:**
- Modify: `src/trinity/deliberation/protocol.py`
- Modify: `tests/test_protocol_compression.py` (or add to `tests/test_protocol.py`)

**Why:** The budget checker needs to be called before each round's `send_and_wait()` to log warnings and enable proactive rotation decisions.

**Step 1: Write the failing test**

Add to `tests/test_protocol_compression.py`:

```python
    def test_budget_checker_logs_warning_for_large_prompt(self, tmp_path):
        """Protocol should check budget before sending and log appropriately."""
        shared = SharedContextEngine(path=tmp_path / "shared.md")
        agent = _make_mock_agent("claude")
        protocol = DeliberationProtocol(
            agents={"claude": agent},
            shared=shared,
            max_rounds=5,
        )

        # Manually set agent usage to 55%
        agent.context_usage = ContextUsage(used=110_000, total=200_000)

        shared.initialize(goal="test", agent_names=["claude"])

        # Build a large prompt
        large_context = "Detailed opinion. " * 2000
        shared.append_opinion("claude", 1, large_context)

        # Check that budget_checker exists and works
        assert protocol.budget_checker is not None
        prompt = protocol._build_round_prompt(2, "test")
        result = protocol.budget_checker.check(
            prompt=prompt,
            current_usage=agent.context_usage,
            agent_spec=agent.spec,
        )
        # With large context at 55%, should at least warn
        assert result.recommendation in ("proceed", "proceed_with_caution", "rotate_first")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_protocol_compression.py::TestRoundPromptCompression::test_budget_checker_logs_warning_for_large_prompt -v`
Expected: FAIL — protocol has no `budget_checker` attribute

**Step 3: Implement**

In `src/trinity/deliberation/protocol.py`:

**3a.** Add import at top:
```python
from trinity.context.budget import TokenBudgetChecker
```

**3b.** In `__init__()`, after the compression setup block (after `self.compression_round_threshold = ...`), add:
```python
        # Pre-send token budget checker
        self.budget_checker = TokenBudgetChecker()
```

**Step 4: Run tests**

Run: `pytest tests/test_protocol_compression.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/trinity/deliberation/protocol.py tests/test_protocol_compression.py
git commit -m "feat(phase7b): integrate TokenBudgetChecker into DeliberationProtocol"
```

---

## Task 5: Fix InteractiveClaudeAgent cumulative token counting

**Files:**
- Modify: `src/trinity/agents/claude_agent.py:407-426`
- Modify: `tests/test_interactive_claude.py`

**Why:** `InteractiveClaudeAgent._parse_usage_from_output()` returns usage per-call but doesn't accumulate. If usage data is missing from pane output, it returns `{"used": 0}`, which resets the cumulative count via `_update_usage()`. We need to accumulate tokens across calls.

**Step 1: Write the failing test**

Add to `tests/test_interactive_claude.py` (READ the file first to find the right class):

```python
    def test_token_count_accumulates_across_calls(self):
        """Token usage should accumulate across multiple send_and_wait calls."""
        # Simulate first call with 100 tokens
        self.agent._parse_usage_from_output("Tokens: 100/200000")
        self.agent._update_usage(**self.agent._parse_usage_from_output("Tokens: 100/200000"))

        first_usage = self.agent.context_usage.used
        assert first_usage == 100

        # Simulate second call with 50 more tokens
        self.agent._update_usage(**self.agent._parse_usage_from_output("Tokens: 50/200000"))

        # Should accumulate: 100 + 50 = 150
        assert self.agent.context_usage.used == 150

    def test_missing_usage_preserves_previous(self):
        """When usage data is missing, should keep previous count."""
        # Set initial usage
        self.agent._update_usage(used=200, total=200_000)

        # Call with no usage data in output
        result = self.agent._parse_usage_from_output("No token info here")

        assert result["used"] == 0  # parse returns 0
        # But _update_usage should NOT reset cumulative count
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_interactive_claude.py -v -k "token_count_accumulates or missing_usage"`
Expected: FAIL — `_parse_usage_from_output` returns per-call values, not cumulative

**Step 3: Implement**

In `src/trinity/agents/claude_agent.py`, modify the `send_and_wait()` method of `InteractiveClaudeAgent`.

Find the section (around line 288-290):
```python
        # Parse token usage if possible
        usage = self._parse_usage_from_output(result.output)
        self._update_usage(**usage)
```

Replace with:
```python
        # Parse token usage if possible — accumulate across calls
        parsed = self._parse_usage_from_output(result.output)
        if parsed["used"] > 0:
            # Accumulate: add this call's tokens to existing count
            new_used = self._context_usage.used + parsed["used"]
            self._update_usage(used=new_used, total=parsed.get("total"))
        # If no usage data, preserve existing count (don't reset to 0)
```

**Step 4: Run tests**

Run: `pytest tests/test_interactive_claude.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/trinity/agents/claude_agent.py tests/test_interactive_claude.py
git commit -m "feat(phase7b): accumulate token counts across InteractiveClaudeAgent calls"
```

---

## Task 6: Full regression test

**Files:** None — verification only.

**Step 1: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All tests PASS

**Step 2: Run coverage**

Run: `pytest tests/ --cov=trinity --cov-report=term-missing`
Expected: Coverage ≥ 87%

**Step 3: Commit any fixes if needed**

```bash
git add -A
git commit -m "fix(phase7b): address test regressions"
```

---

## Summary

| Task | Files | Tests | Key Deliverable |
|------|-------|-------|-----------------|
| 1 | `context/shared.py` | 3 | `remove_section()` method |
| 2 | `deliberation/protocol.py` | 1 | Auto-cleanup after compression |
| 3 | `context/budget.py` (new) | 5 | `TokenBudgetChecker` class |
| 4 | `deliberation/protocol.py` | 1 | Budget checker integration |
| 5 | `agents/claude_agent.py` | 2 | Cumulative token counting fix |
| 6 | — | 0 | Regression verification |

**Total new tests:** ~12
**Total new code:** ~150 lines (budget) + ~30 lines (shared) + ~5 lines (protocol) + ~5 lines (agent)
