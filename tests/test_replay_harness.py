from __future__ import annotations

from trinity.workflow import (
    ExecutionResult,
    ReviewResult,
    ReviewStatus,
    WorkPackage,
    WorkflowPersistence,
    WorkflowSession,
    WorkflowState,
    WorkStatus,
)
from tests.harness.replay import replay_workflow


def test_replay_harness_reconstructs_snapshot_report_and_artifacts(tmp_path) -> None:
    persistence = WorkflowPersistence(tmp_path / ".trinity")
    raw_dir = tmp_path / ".trinity" / "execution" / "WP-001"
    raw_dir.mkdir(parents=True)
    owner_raw = raw_dir / "codex.raw.txt"
    fallback_raw = raw_dir / "claude.raw.txt"
    owner_raw.write_text("owner blocked", encoding="utf-8")
    fallback_raw.write_text("fallback done", encoding="utf-8")
    persistence.save(
        WorkflowSession(
            id="wf-replay",
            goal="Replay workflow",
            state=WorkflowState.POST_REVIEW_READY,
            active_agents=["codex", "claude"],
            work_packages=[
                WorkPackage(
                    id="WP-001",
                    title="Replay package",
                    owner_agent="codex",
                    objective="Exercise replay harness.",
                    status=WorkStatus.DONE,
                    last_executor="claude",
                )
            ],
            execution_results=[
                ExecutionResult(
                    package_id="WP-001",
                    agent_name="claude",
                    status=WorkStatus.DONE,
                    summary="Fallback completed.",
                    raw_response_path=fallback_raw,
                    attempt_chain=[
                        {
                            "agent": "codex",
                            "status": "blocked",
                            "summary": "Owner blocked.",
                            "blockers": ["Missing schema."],
                            "raw_response_path": str(owner_raw),
                        },
                        {
                            "agent": "claude",
                            "status": "done",
                            "summary": "Fallback completed.",
                            "blockers": [],
                            "raw_response_path": str(fallback_raw),
                        },
                    ],
                )
            ],
            review_results=[
                ReviewResult(
                    review_package_id="RP-WP-001-claude",
                    package_id="WP-001",
                    reviewer_agent="claude",
                    target_agent="codex",
                    status=ReviewStatus.APPROVED,
                    summary="Package passes replay review.",
                ).to_dict(),
                ReviewResult(
                    review_package_id="RP-FINAL-claude",
                    package_id="FINAL",
                    reviewer_agent="claude",
                    target_agent="all",
                    status=ReviewStatus.APPROVED,
                    scope="final",
                    summary="Workflow is coherent.",
                ).to_dict(),
            ],
        )
    )
    persistence.append_event(
        {
            "event": "work_package_completed",
            "workflow_id": "wf-replay",
            "data": {
                "package_id": "WP-001",
                "agent": "claude",
                "status": "done",
                "summary": "Fallback completed.",
            },
        }
    )

    replay = replay_workflow(tmp_path)

    assert replay.snapshot.session_id == "wf-replay"
    assert replay.snapshot.work_package_details[0].last_result_attempt_chain[0].startswith(
        "1. `codex` `blocked`"
    )
    assert replay.snapshot.work_package_details[0].review_status == "approved"
    assert replay.snapshot.final_review is not None
    assert replay.snapshot.final_review.summary == "Workflow is coherent."
    assert replay.report.executions[0].attempt_chain[0].startswith("1. codex blocked")
    assert [artifact.path for artifact in replay.report.artifacts] == [
        str(fallback_raw),
        str(owner_raw),
    ]
    assert all(artifact.exists for artifact in replay.report.artifacts)
