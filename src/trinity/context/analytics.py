"""TokenAnalytics — historical usage tracking and prediction."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ANALYTICS_HISTORY_FILENAME = "analytics.jsonl"


def analytics_history_path(state_dir: Path) -> Path:
    """Return the canonical analytics history file for a Trinity state dir."""
    return state_dir / "history" / ANALYTICS_HISTORY_FILENAME


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

    def to_dict(self) -> dict[str, Any]:
        """Serialize this record to a JSON-compatible dict."""
        return {
            "round_num": self.round_num,
            "agent_tokens": dict(self.agent_tokens),
            "prompt_tokens": self.prompt_tokens,
            "duration_seconds": self.duration_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoundRecord":
        """Deserialize a record from JSON-compatible data."""
        agent_tokens = data.get("agent_tokens", {})
        if not isinstance(agent_tokens, dict):
            raise ValueError("agent_tokens must be a mapping")

        return cls(
            round_num=int(data["round_num"]),
            agent_tokens={str(name): int(tokens) for name, tokens in agent_tokens.items()},
            prompt_tokens=int(data.get("prompt_tokens", 0)),
            duration_seconds=float(data.get("duration_seconds", 0.0)),
        )


class TokenAnalytics:
    """Tracks historical token usage and predicts future consumption."""

    def __init__(
        self,
        history_path: Path | None = None,
        load_existing: bool = False,
    ) -> None:
        self._history: list[RoundRecord] = []
        self.history_path = history_path
        if self.history_path and load_existing:
            self._history = self._load_records(self.history_path)

    # -- recording -----------------------------------------------------------

    def record(self, round_record: RoundRecord) -> None:
        """Append a round record to the history."""
        self._history.append(round_record)
        if self.history_path:
            self._append_record(self.history_path, round_record)

    @property
    def history(self) -> list[RoundRecord]:
        """Return the full recorded history."""
        return self._history

    # -- persistence ---------------------------------------------------------

    @classmethod
    def from_file(cls, history_path: Path) -> "TokenAnalytics":
        """Load analytics history from a JSONL file."""
        return cls(history_path=history_path, load_existing=True)

    @staticmethod
    def _append_record(history_path: Path, round_record: RoundRecord) -> None:
        """Append one round record as a JSON line."""
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(round_record.to_dict(), sort_keys=True) + "\n")

    @staticmethod
    def _load_records(history_path: Path) -> list[RoundRecord]:
        """Load persisted records, ignoring blank or malformed lines."""
        if not history_path.exists():
            return []

        records: list[RoundRecord] = []
        for line in history_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    records.append(RoundRecord.from_dict(data))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
        return records

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
