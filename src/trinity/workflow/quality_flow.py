"""Agent quality signal helpers for WorkflowEngine."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from trinity.routing.quality import QualityLedger

if TYPE_CHECKING:
    from trinity.workflow.models import ExecutionResult
    from trinity.workflow.review import ReviewResult


class WorkflowQualityFlow:
    """Record and summarize advisory agent quality signals."""

    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def quality_summaries(self) -> dict[str, dict[str, Any]]:
        """Return advisory quality summaries keyed by agent name."""
        return {
            name: summary.to_dict()
            for name, summary in QualityLedger(
                self.engine.session.quality_signals
            ).summaries().items()
        }

    def record_execution_quality(self, result: "ExecutionResult") -> None:
        ledger = QualityLedger(self.engine.session.quality_signals)
        signal = ledger.record_execution(result)
        self.engine.session.quality_signals = ledger.to_dicts()
        self.engine._persistence_flow().persist(
            "quality_signal_recorded",
            signal.to_dict(),
        )

    def record_review_quality(self, result: "ReviewResult") -> None:
        ledger = QualityLedger(self.engine.session.quality_signals)
        signal = ledger.record_review(result)
        self.engine.session.quality_signals = ledger.to_dicts()
        self.engine._persistence_flow().persist(
            "quality_signal_recorded",
            signal.to_dict(),
        )
