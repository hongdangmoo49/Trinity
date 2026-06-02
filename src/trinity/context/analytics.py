"""TokenAnalytics — historical usage tracking and prediction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RoundRecord:
    """A single round's token usage snapshot."""

    round_num: int
    agent_tokens: dict[str, int]
    prompt_tokens: int
    duration_seconds: float

    @property
    def total_tokens(self) -> int:
        """Sum of all agent token counts."""
        return sum(self.agent_tokens.values())

    @property
    def average_tokens_per_agent(self) -> float:
        """Average tokens across agents for this round."""
        count = len(self.agent_tokens)
        if count == 0:
            return 0.0
        return self.total_tokens / count


class TokenAnalytics:
    """Tracks historical token usage and predicts future consumption."""

    def __init__(self) -> None:
        self._history: list[RoundRecord] = []

    # -- recording -----------------------------------------------------------

    def record(self, round_record: RoundRecord) -> None:
        """Append a round record to the history."""
        self._history.append(round_record)

    @property
    def history(self) -> list[RoundRecord]:
        """Return the full recorded history."""
        return self._history

    # -- aggregate properties ------------------------------------------------

    @property
    def total_session_tokens(self) -> int:
        """Sum of total_tokens across all recorded rounds."""
        return sum(r.total_tokens for r in self._history)

    @property
    def average_tokens_per_round(self) -> float:
        """Average total tokens per round."""
        if not self._history:
            return 0.0
        return self.total_session_tokens / len(self._history)

    # -- per-agent analytics -------------------------------------------------

    def agent_burn_rate(self, name: str) -> float:
        """Average tokens consumed by *name* per recorded round."""
        if not self._history:
            return 0.0
        total = sum(r.agent_tokens.get(name, 0) for r in self._history)
        return total / len(self._history)

    def projected_remaining_rounds(
        self,
        name: str,
        current_used: int,
        total_budget: int,
    ) -> float:
        """Estimate how many rounds remain before *total_budget* is exhausted.

        Returns *float('inf')* when there is no burn history for the agent.
        """
        burn = self.agent_burn_rate(name)
        if burn == 0:
            return float("inf")
        remaining_budget = total_budget - current_used
        return remaining_budget / burn

    def is_high_burn_session(
        self,
        name: str,
        total_budget: int,
        threshold_rounds: float = 5.0,
    ) -> bool:
        """Return True if the session is consuming budget faster than *threshold_rounds*."""
        if not self._history:
            return False
        burn = self.agent_burn_rate(name)
        if burn == 0:
            return False
        projected_total_rounds = total_budget / burn
        return projected_total_rounds < threshold_rounds

    # -- trend detection -----------------------------------------------------

    def trend(self) -> str:
        """Compare first-half vs second-half token totals.

        Returns ``"increasing"`` if the second half is >1.2x the first,
        ``"decreasing"`` if <0.8x, otherwise ``"stable"``.
        """
        if len(self._history) < 2:
            return "stable"

        mid = len(self._history) // 2
        first_half_total = sum(r.total_tokens for r in self._history[:mid])
        second_half_total = sum(r.total_tokens for r in self._history[mid:])

        if first_half_total == 0:
            return "stable" if second_half_total == 0 else "increasing"

        ratio = second_half_total / first_half_total
        if ratio > 1.2:
            return "increasing"
        if ratio < 0.8:
            return "decreasing"
        return "stable"

    # -- summary -------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Return a summary dict of the session so far."""
        agents: dict[str, dict[str, Any]] = {}
        all_names: set[str] = set()
        for r in self._history:
            all_names.update(r.agent_tokens.keys())

        for name in sorted(all_names):
            agents[name] = {
                "burn_rate": self.agent_burn_rate(name),
                "total": sum(r.agent_tokens.get(name, 0) for r in self._history),
            }

        return {
            "rounds_recorded": len(self._history),
            "total_tokens": self.total_session_tokens,
            "avg_tokens_per_round": self.average_tokens_per_round,
            "trend": self.trend(),
            "agents": agents,
        }
