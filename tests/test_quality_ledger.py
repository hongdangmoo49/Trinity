"""Tests for advisory agent quality signals."""

from trinity.routing.quality import QualityLedger, QualitySignal
from trinity.workflow.engine import WorkflowEngine
from trinity.workflow.models import ExecutionResult, WorkPackage, WorkStatus
from trinity.workflow.review import ReviewResult, ReviewStatus


def test_quality_ledger_records_execution_and_review_signals():
    ledger = QualityLedger()
    execution_signal = ledger.record_execution(
        ExecutionResult(
            package_id="WP-001",
            agent_name="codex",
            status=WorkStatus.DONE,
            files_changed=["src/app.py"],
        )
    )
    review_signal = ledger.record_review(
        ReviewResult(
            review_package_id="RP-WP-001-claude",
            package_id="WP-001",
            reviewer_agent="claude",
            target_agent="codex",
            status=ReviewStatus.CHANGES_REQUESTED,
            required_changes=["Add test"],
        )
    )

    assert execution_signal.success is True
    assert review_signal.success is False
    summaries = ledger.summaries()
    assert summaries["codex"].success_count == 1
    assert summaries["claude"].required_change_count == 1
    assert summaries["claude"].score < 0


def test_quality_signal_round_trips_dict():
    signal = QualitySignal(
        agent_name="codex",
        source="execution",
        package_id="WP-001",
        status="done",
        success=True,
        files_changed_count=2,
        score_delta=1.0,
    )

    restored = QualitySignal.from_dict(signal.to_dict())

    assert restored.agent_name == "codex"
    assert restored.source == "execution"
    assert restored.files_changed_count == 2
    assert restored.score_delta == 1.0


def test_workflow_engine_persists_quality_signals(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.session.active_agents = ["codex", "claude"]
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="Implementation",
            owner_agent="codex",
            objective="Implement feature.",
        )
    ]

    engine.record_execution_results(
        [
            ExecutionResult(
                package_id="WP-001",
                agent_name="codex",
                status=WorkStatus.DONE,
                files_changed=["src/app.py"],
            )
        ]
    )
    engine.record_review_results(
        [
            ReviewResult(
                review_package_id="RP-WP-001-claude",
                package_id="WP-001",
                reviewer_agent="claude",
                target_agent="codex",
                status=ReviewStatus.APPROVED,
            )
        ]
    )

    loaded = WorkflowEngine(tmp_path / ".trinity")

    assert len(loaded.session.quality_signals) == 2
    summaries = loaded.quality_summaries()
    assert summaries["codex"]["success_count"] == 1
    assert summaries["claude"]["success_count"] == 1
