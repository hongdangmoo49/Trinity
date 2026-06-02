# Phase 7C: Token Usage Analytics & Prediction

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Track per-round token usage per agent, compute historical averages/trends, and predict whether the current session will exceed context budget — enabling proactive optimization decisions.

**Architecture:** Create a `TokenAnalytics` class that accumulates `RoundRecord` data (tokens per agent per round, prompt sizes, timing) in memory during a deliberation session. It computes per-agent burn rates, projected depletion time, and session-wide statistics. Integrated into `DeliberationProtocol.run()` to record after each round, and exposed via `TrinityOrchestrator.get_analytics()`.

**Tech Stack:** Python 3.10+, dataclasses, no new dependencies.

---

## Task 1: Create `RoundRecord` and `TokenAnalytics` core

**Files:**
- Create: `src/trinity/context/analytics.py`
- Create: `tests/test_analytics.py`

**Step 1: Write the failing tests**

Create `tests/test_analytics.py`:

```python
"""Tests for TokenAnalytics — historical usage tracking and prediction."""

import pytest

from trinity.context.analytics import TokenAnalytics, RoundRecord


class TestRoundRecord:
    def test_creation(self):
        r = RoundRecord(round_num=1, agent_tokens={"claude": 500, "codex": 300}, prompt_tokens=200, duration_seconds=2.5)
        assert r.round_num == 1
        assert r.total_tokens == 800

    def test_total_tokens_sums_agents(self):
        r = RoundRecord(round_num=2, agent_tokens={"claude": 1000}, prompt_tokens=400, duration_seconds=5.0)
        assert r.total_tokens == 1000

    def test_average_tokens_per_agent(self):
        r = RoundRecord(round_num=1, agent_tokens={"claude": 600, "codex": 400}, prompt_tokens=200, duration_seconds=3.0)
        assert r.average_tokens_per_agent == 500.0


class TestTokenAnalytics:

    def test_record_and_get_history(self):
        analytics = TokenAnalytics()
        analytics.record(RoundRecord(1, {"claude": 500}, 100, 2.0))
        analytics.record(RoundRecord(2, {"claude": 600}, 150, 3.0))
        assert len(analytics.history) == 2
        assert analytics.history[0].round_num == 1

    def test_total_session_tokens(self):
        analytics = TokenAnalytics()
        analytics.record(RoundRecord(1, {"claude": 500}, 100, 2.0))
        analytics.record(RoundRecord(2, {"claude": 700}, 200, 3.0))
        assert analytics.total_session_tokens == 1200

    def test_average_tokens_per_round(self):
        analytics = TokenAnalytics()
        analytics.record(RoundRecord(1, {"claude": 400}, 100, 2.0))
        analytics.record(RoundRecord(2, {"claude": 600}, 200, 3.0))
        assert analytics.average_tokens_per_round == 500.0

    def test_agent_burn_rate(self):
        """Tokens per round for a specific agent."""
        analytics = TokenAnalytics()
        analytics.record(RoundRecord(1, {"claude": 300, "codex": 200}, 100, 2.0))
        analytics.record(RoundRecord(2, {"claude": 500, "codex": 300}, 150, 3.0))
        assert analytics.agent_burn_rate("claude") == 400.0
        assert analytics.agent_burn_rate("codex") == 250.0

    def test_projected_depletion_rounds(self):
        """How many more rounds until agent hits context limit."""
        analytics = TokenAnalytics()
        analytics.record(RoundRecord(1, {"claude": 40000}, 100, 2.0))
        analytics.record(RoundRecord(2, {"claude": 40000}, 150, 3.0))
        # Agent uses ~40K tokens/round, budget 200K, already used 80K
        # Remaining: 120K, at 40K/round = 3 more rounds
        remaining = analytics.projected_remaining_rounds("claude", current_used=80000, total_budget=200000)
        assert remaining == 3.0

    def test_projected_depletion_unlimited(self):
        """No history means we can't predict."""
        analytics = TokenAnalytics()
        assert analytics.projected_remaining_rounds("claude", 1000, 200000) == float("inf")

    def test_is_high_burn_session(self):
        """Detect if current session burns more than 1.5x average."""
        analytics = TokenAnalytics()
        analytics.record(RoundRecord(1, {"claude": 50000}, 100, 2.0))
        analytics.record(RoundRecord(2, {"claude": 50000}, 150, 3.0))
        # At 50K/round, for 200K budget = 4 rounds to fill = high burn
        assert analytics.is_high_burn_session("claude", total_budget=200000) is True

    def test_is_not_high_burn_session(self):
        analytics = TokenAnalytics()
        analytics.record(RoundRecord(1, {"claude": 5000}, 100, 2.0))
        analytics.record(RoundRecord(2, {"claude": 5000}, 150, 3.0))
        # At 5K/round, for 200K budget = 40 rounds = low burn
        assert analytics.is_high_burn_session("claude", total_budget=200000) is False

    def test_summary_dict(self):
        """summary() returns a dict with all analytics."""
        analytics = TokenAnalytics()
        analytics.record(RoundRecord(1, {"claude": 5000}, 200, 2.0))
        s = analytics.summary()
        assert "total_tokens" in s
        assert "rounds_recorded" in s
        assert "avg_tokens_per_round" in s
        assert s["rounds_recorded"] == 1

    def test_trend_direction(self):
        """Detect if token usage is increasing, decreasing, or stable."""
        analytics = TokenAnalytics()
        analytics.record(RoundRecord(1, {"claude": 1000}, 100, 2.0))
        analytics.record(RoundRecord(2, {"claude": 2000}, 200, 3.0))
        analytics.record(RoundRecord(3, {"claude": 3000}, 300, 4.0))
        assert analytics.trend() == "increasing"

    def test_trend_stable(self):
        analytics = TokenAnalytics()
        analytics.record(RoundRecord(1, {"claude": 1000}, 100, 2.0))
        analytics.record(RoundRecord(2, {"claude": 1050}, 100, 2.0))
        assert analytics.trend() == "stable"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_analytics.py -v`
Expected: FAIL — module does not exist

**Step 3: Implement**

Create `src/trinity/context/analytics.py`:

```python
"""Token usage analytics — track historical patterns and predict future usage."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RoundRecord:
    """Token usage record for a single deliberation round."""

    round_num: int
    agent_tokens: dict[str, int]  # agent_name → tokens consumed this round
    prompt_tokens: int  # tokens in the prompt sent to agents
    duration_seconds: float = 0.0

    @property
    def total_tokens(self) -> int:
        """Total tokens consumed by all agents this round."""
        return sum(self.agent_tokens.values())

    @property
    def average_tokens_per_agent(self) -> float:
        """Average tokens per agent this round."""
        if not self.agent_tokens:
            return 0.0
        return self.total_tokens / len(self.agent_tokens)


class TokenAnalytics:
    """Track token usage across deliberation rounds and compute predictions.

    Records per-round usage, computes burn rates, detects high-burn
    sessions, and predicts when agents will run out of context budget.

    Usage:
        analytics = TokenAnalytics()
        analytics.record(RoundRecord(1, {"claude": 5000}, 200, 2.0))
        analytics.record(RoundRecord(2, {"claude": 6000}, 300, 3.0))

        # Predictions
        analytics.projected_remaining_rounds("claude", 11000, 200000)
        analytics.is_high_burn_session("claude", 200000)
        analytics.trend()
    """

    def __init__(self):
        self.history: list[RoundRecord] = []

    def record(self, round_record: RoundRecord) -> None:
        """Record a completed round's token usage."""
        self.history.append(round_record)
        logger.info(
            f"Round {round_record.round_num} analytics: "
            f"{round_record.total_tokens:,} tokens, "
            f"{round_record.duration_seconds:.1f}s"
        )

    @property
    def total_session_tokens(self) -> int:
        """Total tokens consumed across all rounds."""
        return sum(r.total_tokens for r in self.history)

    @property
    def average_tokens_per_round(self) -> float:
        """Average tokens per round."""
        if not self.history:
            return 0.0
        return self.total_session_tokens / len(self.history)

    def agent_burn_rate(self, agent_name: str) -> float:
        """Average tokens per round for a specific agent."""
        tokens = [r.agent_tokens.get(agent_name, 0) for r in self.history]
        if not tokens:
            return 0.0
        return sum(tokens) / len(tokens)

    def projected_remaining_rounds(
        self, agent_name: str, current_used: int, total_budget: int
    ) -> float:
        """Predict how many more rounds before the agent hits its budget.

        Returns float("inf") if no history or burn rate is 0.
        """
        burn_rate = self.agent_burn_rate(agent_name)
        if burn_rate <= 0:
            return float("inf")

        remaining = max(0, total_budget - current_used)
        return remaining / burn_rate

    def is_high_burn_session(
        self, agent_name: str, total_budget: int, threshold_rounds: float = 5.0
    ) -> bool:
        """Detect if the session is burning tokens faster than expected.

        A session is 'high burn' if the projected depletion is fewer than
        threshold_rounds from the start (i.e., the agent would fill its
        context in very few rounds).

        Args:
            agent_name: Agent to check.
            total_budget: Agent's total context budget.
            threshold_rounds: Minimum rounds-to-fill to be considered high burn.
        """
        if not self.history:
            return False

        burn_rate = self.agent_burn_rate(agent_name)
        if burn_rate <= 0:
            return False

        rounds_to_fill = total_budget / burn_rate
        return rounds_to_fill < threshold_rounds

    def trend(self) -> str:
        """Detect token usage trend: 'increasing', 'decreasing', or 'stable'.

        Compares first half to second half of recorded rounds.
        Requires at least 2 rounds.
        """
        if len(self.history) < 2:
            return "stable"

        mid = len(self.history) // 2
        first_half = sum(r.total_tokens for r in self.history[:mid])
        second_half = sum(r.total_tokens for r in self.history[mid:])

        if first_half == 0:
            return "stable"

        ratio = second_half / first_half
        if ratio > 1.2:
            return "increasing"
        elif ratio < 0.8:
            return "decreasing"
        else:
            return "stable"

    def summary(self) -> dict:
        """Return a summary dict of analytics."""
        return {
            "rounds_recorded": len(self.history),
            "total_tokens": self.total_session_tokens,
            "avg_tokens_per_round": self.average_tokens_per_round,
            "trend": self.trend(),
            "agents": {
                name: {
                    "total": sum(r.agent_tokens.get(name, 0) for r in self.history),
                    "burn_rate": self.agent_burn_rate(name),
                }
                for name in self._all_agent_names()
            },
        }

    def _all_agent_names(self) -> set[str]:
        """Collect all agent names seen across rounds."""
        names: set[str] = set()
        for r in self.history:
            names.update(r.agent_tokens.keys())
        return names
```

**Step 4: Run tests**

Run: `pytest tests/test_analytics.py -v`
Expected: All 12 tests PASS

**Step 5: Commit**

```bash
git add src/trinity/context/analytics.py tests/test_analytics.py
git commit -m "feat(phase7c): add TokenAnalytics with usage tracking and prediction"
```

---

## Task 2: Integrate analytics into DeliberationProtocol

**Files:**
- Modify: `src/trinity/deliberation/protocol.py`
- Modify: `tests/test_protocol.py` (or add to existing)

**Step 1: Write the failing test**

Add to `tests/test_protocol.py` or `tests/test_protocol_compression.py`:

```python
    def test_analytics_recorded_after_run(self, tmp_path):
        """Protocol should record analytics after each round."""
        shared = SharedContextEngine(path=tmp_path / "shared.md")
        agent = _make_mock_agent("claude", "I agree with this approach.")
        protocol = DeliberationProtocol(
            agents={"claude": agent},
            shared=shared,
            max_rounds=3,
        )
        shared.initialize(goal="test", agent_names=["claude"])

        import asyncio
        result = asyncio.run(protocol.run("test question"))

        assert result.rounds_completed >= 1
        assert protocol.analytics is not None
        assert len(protocol.analytics.history) >= 1
        assert protocol.analytics.total_session_tokens > 0
```

**Step 2: Run test to verify it fails**

**Step 3: Implement**

In `src/trinity/deliberation/protocol.py`:

Add import:
```python
from trinity.context.analytics import TokenAnalytics, RoundRecord
```

In `__init__()`, add:
```python
        self.analytics = TokenAnalytics()
```

In `run()`, after `# Write opinions to shared.md` block (around line 105), add token tracking:

After this existing block:
```python
            # Write opinions to shared.md
            for name, msg in opinions.items():
                self.shared.append_opinion(name, round_num, msg.content)
```

Add:
```python
            # Record token analytics for this round
            round_agent_tokens = {name: msg.token_count for name, msg in opinions.items()}
            round_prompt_tokens = self.compressor.estimate_tokens(round_prompt) if self.compressor else len(round_prompt.split())
            self.analytics.record(RoundRecord(
                round_num=round_num,
                agent_tokens=round_agent_tokens,
                prompt_tokens=round_prompt_tokens,
                duration_seconds=time.time() - start_time,
            ))
```

**Step 4: Run tests**

**Step 5: Commit**

```bash
git add src/trinity/deliberation/protocol.py tests/test_protocol_compression.py
git commit -m "feat(phase7c): integrate TokenAnalytics into DeliberationProtocol"
```

---

## Task 3: Expose analytics via Orchestrator and CLI

**Files:**
- Modify: `src/trinity/orchestrator.py`
- Modify: `src/trinity/cli.py`
- Modify: `tests/test_cli.py`

**Step 1: Write failing test**

Add to `tests/test_cli.py`:

```python
def test_analytics_command(tmp_path):
    """trinity analytics should show usage summary."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["analytics"])
        # Without a running session, should show empty or help message
        assert result.exit_code == 0
```

**Step 2: Run test, verify fail**

**Step 3: Implement**

In `orchestrator.py`, add method:

```python
    def get_analytics(self) -> dict | None:
        """Return token analytics summary if available."""
        if self.protocol and self.protocol.analytics.history:
            return self.protocol.analytics.summary()
        return None
```

In `cli.py`, add command:

```python
@main.command()
def analytics():
    """Show token usage analytics for the current session."""
    config = load_config()
    orchestrator = TrinityOrchestrator(config)

    summary = orchestrator.get_analytics()
    if not summary:
        console.print("[yellow]No analytics data available. Run a deliberation first.[/yellow]")
        return

    console.print(Panel.fit(
        f"Rounds: {summary['rounds_recorded']}\n"
        f"Total tokens: {summary['total_tokens']:,}\n"
        f"Avg tokens/round: {summary['avg_tokens_per_round']:,.0f}\n"
        f"Trend: {summary['trend']}",
        title="Token Analytics",
    ))

    if summary.get("agents"):
        table = Table(title="Agent Usage")
        table.add_column("Agent", style="cyan")
        table.add_column("Total Tokens", justify="right")
        table.add_column("Burn Rate (tokens/round)", justify="right")

        for name, data in summary["agents"].items():
            table.add_row(
                name,
                f"{data['total']:,}",
                f"{data['burn_rate']:,.0f}",
            )
        console.print(table)
```

**Step 4: Run tests**

**Step 5: Commit**

```bash
git add src/trinity/orchestrator.py src/trinity/cli.py tests/test_cli.py
git commit -m "feat(phase7c): expose token analytics via orchestrator and CLI"
```

---

## Task 4: Full regression test

**Step 1:** Run `pytest tests/ -q --tb=short`
**Step 2:** Commit fixes if needed

---

## Summary

| Task | Files | Tests | Deliverable |
|------|-------|-------|-------------|
| 1 | `context/analytics.py` (new) | 12 | `RoundRecord` + `TokenAnalytics` core |
| 2 | `deliberation/protocol.py` | 1 | Per-round analytics recording |
| 3 | `orchestrator.py`, `cli.py` | 1 | `trinity analytics` CLI command |
| 4 | — | 0 | Regression verification |
