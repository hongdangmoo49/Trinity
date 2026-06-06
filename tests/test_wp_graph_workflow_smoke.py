"""Smoke tests for central WP graph planning through UI projection."""

from trinity.config import TrinityConfig
from trinity.models import ConsensusResult, DeliberationResult
from trinity.textual_app.snapshot import NexusSnapshotAdapter
from trinity.workflow import WorkflowEngine, WorkflowState


def test_wp_graph_request_to_execution_matrix_log_smoke(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    engine = WorkflowEngine(config.effective_state_dir)

    action = engine.handle_user_input(
        "테스트 가능한 Textual 도구를 만들어라",
        ["claude", "codex"],
    )
    assert action.should_deliberate is True
    assert engine.state == WorkflowState.DELIBERATING

    engine.mark_deliberation_result(
        DeliberationResult(
            user_prompt=action.prompt,
            rounds_completed=1,
            consensus=ConsensusResult(
                reached=True,
                agreement_count=2,
                total_agents=2,
                opinions={"claude": "approve", "codex": "approve"},
                summary="중앙 WP graph를 포함한 blueprint.",
            ),
            metadata={
                "structured_consensus": {
                    "reached": True,
                    "final_blueprint": {
                        "title": "Textual Tool",
                        "summary": "테스트 가능한 Textual 도구.",
                        "acceptance_criteria": ["실행 로그가 표시된다."],
                        "work_packages": [
                            {
                                "id": "ui-shell",
                                "title": "UI shell",
                                "owner_agent": "missing",
                                "objective": "Build the Textual shell.",
                                "scope": ["Nexus and execution screens"],
                                "dependencies": ["missing-dependency"],
                                "expected_files": [],
                                "parallel_group": 1,
                                "parallelizable": True,
                                "risk": "extreme",
                            }
                        ],
                    },
                    "open_questions": [],
                }
            },
        )
    )

    assert engine.state == WorkflowState.BLUEPRINT_READY
    assert engine.work_packages[0].repair_notes

    engine.set_target_workspace(tmp_path / "target")
    enable_action = engine.enable_execution_for_current_blueprint("테스트를 해라")
    assert enable_action.execution_requested is True

    engine.begin_execution()
    engine.record_execution_batch_planned(
        [["WP-001"]],
        notices=[
            {
                "reason": "expected_files missing; using unknown write scope",
                "serialized_agents": ["claude"],
            }
        ],
    )
    engine.record_work_package_started("WP-001", "claude", occurred_at=1710000000.0)
    engine.record_work_package_completed(
        "WP-001",
        "claude",
        status="done",
        summary="Smoke execution completed.",
        occurred_at=1710000060.0,
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    assert snapshot.state == "executing"
    assert snapshot.central_work_packages[0].startswith("ui-shell missing: UI shell")
    assert snapshot.work_package_repairs
    assert any("execution_batch_planned: 1 batches" in line for line in snapshot.execution_log)
    assert any(
        "work_package_started: WP-001 claude running" in line
        for line in snapshot.execution_log
    )
    assert any(
        "work_package_completed: WP-001 claude done" in line
        for line in snapshot.execution_log
    )
