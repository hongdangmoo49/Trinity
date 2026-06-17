"""Advisory agent quality signals for future routing decisions."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from trinity.workflow.models import ExecutionResult
    from trinity.workflow.review import ReviewResult


@dataclass(frozen=True)
class QualitySignal:
    """One observed quality signal for an agent turn."""

    agent_name: str
    source: str
    package_id: str
    status: str
    success: bool
    blockers_count: int = 0
    required_changes_count: int = 0
    files_changed_count: int = 0
    severity: str = ""
    score_delta: float = 0.0
    observed_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "source": self.source,
            "package_id": self.package_id,
            "status": self.status,
            "success": self.success,
            "blockers_count": self.blockers_count,
            "required_changes_count": self.required_changes_count,
            "files_changed_count": self.files_changed_count,
            "severity": self.severity,
            "score_delta": self.score_delta,
            "observed_at": self.observed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QualitySignal":
        return cls(
            agent_name=str(data.get("agent_name", "")),
            source=str(data.get("source", "")),
            package_id=str(data.get("package_id", "")),
            status=str(data.get("status", "")),
            success=bool(data.get("success", False)),
            blockers_count=int(data.get("blockers_count", 0) or 0),
            required_changes_count=int(data.get("required_changes_count", 0) or 0),
            files_changed_count=int(data.get("files_changed_count", 0) or 0),
            severity=str(data.get("severity", "")),
            score_delta=float(data.get("score_delta", 0.0) or 0.0),
            observed_at=float(data.get("observed_at", time.time()) or time.time()),
        )


@dataclass(frozen=True)
class AgentQualitySummary:
    """Aggregated advisory score for one agent."""

    agent_name: str
    signal_count: int
    success_count: int
    blocker_count: int
    required_change_count: int
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "signal_count": self.signal_count,
            "success_count": self.success_count,
            "blocker_count": self.blocker_count,
            "required_change_count": self.required_change_count,
            "score": self.score,
        }


class QualityLedger:
    """Small in-memory helper for quality signal recording and aggregation."""

    def __init__(self, signals: list[dict[str, Any]] | None = None):
        self.signals = [
            QualitySignal.from_dict(item)
            for item in signals or []
            if isinstance(item, dict)
        ]

    def record_execution(self, result: "ExecutionResult") -> QualitySignal:
        status = str(getattr(result.status, "value", result.status))
        success = status in {"done", "needs_review"}
        blockers = len(result.blockers)
        signal = QualitySignal(
            agent_name=result.agent_name,
            source="execution",
            package_id=result.package_id,
            status=status,
            success=success,
            blockers_count=blockers,
            files_changed_count=len(result.files_changed),
            score_delta=1.0 if success else -(1.0 + blockers),
        )
        self.signals.append(signal)
        return signal

    def record_review(self, result: "ReviewResult") -> QualitySignal:
        status = str(getattr(result.status, "value", result.status))
        success = status == "approved"
        required_changes = len(result.required_changes)
        signal = QualitySignal(
            agent_name=result.reviewer_agent,
            source="review",
            package_id=result.package_id,
            status=status,
            success=success,
            required_changes_count=required_changes,
            severity=result.severity,
            score_delta=1.0 if success else -(0.5 + required_changes),
        )
        self.signals.append(signal)
        return signal

    def to_dicts(self) -> list[dict[str, Any]]:
        return [signal.to_dict() for signal in self.signals]

    def summaries(self) -> dict[str, AgentQualitySummary]:
        grouped: dict[str, list[QualitySignal]] = {}
        for signal in self.signals:
            if signal.agent_name:
                grouped.setdefault(signal.agent_name, []).append(signal)
        summaries: dict[str, AgentQualitySummary] = {}
        for agent_name, signals in grouped.items():
            success_count = sum(1 for signal in signals if signal.success)
            blocker_count = sum(signal.blockers_count for signal in signals)
            required_change_count = sum(
                signal.required_changes_count for signal in signals
            )
            score = sum(signal.score_delta for signal in signals) / max(1, len(signals))
            summaries[agent_name] = AgentQualitySummary(
                agent_name=agent_name,
                signal_count=len(signals),
                success_count=success_count,
                blocker_count=blocker_count,
                required_change_count=required_change_count,
                score=round(score, 3),
            )
        return summaries
