from __future__ import annotations

import os
from datetime import datetime

from trinity.config import TrinityConfig
from trinity.context.shared import SharedContextEngine
from trinity.textual_app.snapshot import NexusSnapshotAdapter
from trinity.tui.events import TUIEvent, TUIEventType
from trinity.workflow import (
    Blueprint,
    ExecutionResult,
    OpenQuestion,
    WorkflowPersistence,
    WorkflowSession,
    WorkflowState,
    WorkPackage,
    WorkStatus,
    DecisionRecord,
)


def test_snapshot_loads_provider_defaults_without_workflow(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    assert snapshot.state == "idle"
    assert [provider.name for provider in snapshot.providers] == [
        "claude",
        "codex",
        "antigravity",
    ]
    assert snapshot.providers[0].status == "Queued"
    assert snapshot.providers[1].status == "Disabled"


def test_snapshot_does_not_project_stale_agreed_conclusion_without_workflow(
    tmp_path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    SharedContextEngine(config.shared_context_path).update_consensus(
        "Old agreed conclusion from a previous run."
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    assert snapshot.state == "idle"
    assert snapshot.synthesis.summary == ""
    assert snapshot.synthesis.consensus_progress == ""


def test_snapshot_projects_persisted_workflow(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-textual",
            goal="Build UI",
            state=WorkflowState.BLUEPRINT_READY,
            active_agents=["claude"],
            current_round=2,
            pending_questions=[OpenQuestion(id="q-1", question="Which theme?", options=["dark"])],
            blueprint=Blueprint(
                title="Workbench",
                summary="Use Textual screens.",
                data_flow=["prompt -> nexus"],
            ),
        )
    )
    persistence.append_event(
        {
            "event": "state_changed",
            "state": "blueprint_ready",
            "workflow_id": "wf-textual",
        }
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    assert snapshot.session_id == "wf-textual"
    assert snapshot.goal == "Build UI"
    assert snapshot.state == "blueprint_ready"
    assert snapshot.synthesis.summary == "Use Textual screens."
    assert [question.question for question in snapshot.questions] == ["Which theme?"]
    assert snapshot.questions[0].options == ["dark"]
    assert snapshot.workflow_events == ["state_changed: blueprint_ready"]
    assert snapshot.execution_log == ["state_changed: blueprint_ready"]
    assert snapshot.providers[0].enabled is True
    assert snapshot.providers[1].enabled is False


def test_snapshot_projects_central_and_repaired_work_package_graph(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    missing_dependency_note = "dependency 'shared-contract' removed because no package matched"
    persistence.save(
        WorkflowSession(
            id="wf-graph",
            goal="Build UI",
            state=WorkflowState.BLUEPRINT_READY,
            active_agents=["claude", "codex"],
            blueprint=Blueprint(
                title="Workbench",
                summary="Use Textual screens.",
                work_packages=[
                    WorkPackage(
                        id="frontend",
                        title="Frontend shell",
                        owner_agent="missing",
                        objective="Build the shell.",
                        dependencies=["shared-contract"],
                        expected_files=[],
                    )
                ],
            ),
            work_packages=[
                WorkPackage(
                    id="WP-001",
                    title="Frontend shell",
                    owner_agent="claude",
                    objective="Build the shell.",
                    expected_files=["__trinity_unknown_write_scope__"],
                    repair_notes=[
                        "id normalized from 'frontend' to 'WP-001'",
                        "owner reassigned from 'missing' to 'claude'",
                        missing_dependency_note,
                    ],
                )
            ],
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    assert snapshot.central_work_packages == [
        "frontend missing: Frontend shell (deps=shared-contract; files=-)"
    ]
    assert snapshot.work_packages == ["WP-001 claude: Frontend shell (pending)"]
    assert snapshot.work_package_repairs == [
        "WP-001: id normalized from 'frontend' to 'WP-001'",
        "WP-001: owner reassigned from 'missing' to 'claude'",
        f"WP-001: {missing_dependency_note}",
    ]


def test_snapshot_keeps_answered_question_history(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-questions",
            goal="Build game",
            state=WorkflowState.BLUEPRINT_READY,
            active_agents=["claude"],
            pending_questions=[
                OpenQuestion(
                    id="q-1",
                    question="Engine?",
                    options=["Godot", "Unity"],
                    status="answered",
                ),
                OpenQuestion(
                    id="q-2",
                    question="Platform?",
                    options=["PC", "Mobile"],
                ),
            ],
            decisions=[
                DecisionRecord(
                    id="dec-001",
                    question_id="q-1",
                    decision="Godot",
                    decided_by="user",
                )
            ],
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    assert [question.question for question in snapshot.questions] == [
        "Engine?",
        "Platform?",
    ]
    assert snapshot.questions[0].status == "answered"
    assert snapshot.questions[0].answer == "Godot"
    assert snapshot.questions[1].status == "open"
    assert snapshot.questions[1].answer == ""


def test_snapshot_does_not_attach_stale_answer_to_open_duplicate_question(
    tmp_path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-questions",
            goal="Build bot",
            state=WorkflowState.NEEDS_USER_DECISION,
            active_agents=["codex"],
            pending_questions=[
                OpenQuestion(
                    id="oq-001",
                    question="Capital range?",
                    options=["small", "medium"],
                    status="answered",
                ),
                OpenQuestion(
                    id="oq-001",
                    question="Broker API style?",
                    options=["REST", "COM/OCX"],
                    status="open",
                ),
            ],
            decisions=[
                DecisionRecord(
                    id="dec-001",
                    question_id="oq-001",
                    decision="medium",
                    decided_by="user",
                )
            ],
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    assert snapshot.questions[0].answer == "medium"
    assert snapshot.questions[1].status == "open"
    assert snapshot.questions[1].answer == ""


def test_snapshot_formats_execution_events_with_runtime_details(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    started_at = 1710000000.0
    completed_at = 1710000060.0
    started_prefix = datetime.fromtimestamp(started_at).strftime("[%H:%M:%S]")
    completed_prefix = datetime.fromtimestamp(completed_at).strftime("[%H:%M:%S]")
    persistence.save(
        WorkflowSession(
            id="wf-execution",
            goal="Build game",
            state=WorkflowState.EXECUTING,
            active_agents=["claude", "codex"],
            work_packages=[
                WorkPackage(
                    id="WP-001",
                    title="InputController",
                    owner_agent="claude",
                    objective="Build input controller.",
                )
            ],
        )
    )
    persistence.append_event(
        {
            "event": "implementation_requested",
            "state": "blueprint_ready",
            "workflow_id": "wf-execution",
            "data": {
                "target_workspace": "/workspace/game",
                "work_packages": ["WP-001"],
            },
        }
    )
    persistence.append_event(
        {
            "event": "work_package_started",
            "state": "executing",
            "workflow_id": "wf-execution",
            "data": {
                "package_id": "WP-001",
                "agent": "claude",
                "status": "running",
            },
            "timestamp": started_at,
        }
    )
    persistence.append_event(
        {
            "event": "execution_batch_planned",
            "state": "executing",
            "workflow_id": "wf-execution",
            "data": {
                "batches": [["WP-001"], ["WP-002"]],
                "notices": [
                    {
                        "reason": "high-risk package serialized",
                        "serialized_agents": ["claude", "codex"],
                    }
                ],
            },
        }
    )
    persistence.append_event(
        {
            "event": "work_package_completed",
            "state": "executing",
            "workflow_id": "wf-execution",
            "data": {
                "package_id": "WP-001",
                "agent": "claude",
                "status": "done",
                "summary": "Implemented input controller.",
            },
            "timestamp": completed_at,
        }
    )
    persistence.append_event(
        {
            "event": "execution_result_recorded",
            "state": "executing",
            "workflow_id": "wf-execution",
            "data": {
                "package_id": "WP-001",
                "agent": "claude",
                "status": "done",
            },
        }
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    assert snapshot.execution_log == [
        "implementation_requested: 1 packages -> /workspace/game",
        f"{started_prefix} work_package_started: WP-001 claude running",
        ("execution_batch_planned: 2 batches; 1 policy notices - high-risk package serialized"),
        (
            f"{completed_prefix} work_package_completed: "
            "WP-001 claude done - Implemented input controller."
        ),
    ]


def test_snapshot_projects_execution_recovery_and_executor_details(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-interrupted",
            goal="Build game",
            state=WorkflowState.EXECUTING,
            active_agents=["codex", "claude"],
            target_workspace=tmp_path / "game",
            work_packages=[
                WorkPackage(
                    id="WP-001",
                    title="Shared contracts",
                    owner_agent="codex",
                    objective="Build contracts.",
                    scope=["Define API"],
                    expected_files=["src/contracts.py"],
                    acceptance_criteria=["Types compile"],
                    status=WorkStatus.RUNNING,
                    current_executor="claude",
                    last_executor="claude",
                    risk="high",
                ),
                WorkPackage(
                    id="WP-002",
                    title="Done package",
                    owner_agent="codex",
                    objective="Done.",
                    status=WorkStatus.DONE,
                    last_executor="codex",
                ),
            ],
            execution_results=[
                ExecutionResult(
                    package_id="WP-001",
                    agent_name="claude",
                    status=WorkStatus.FAILED,
                    summary="Could not finish.",
                    files_changed=["src/contracts.py"],
                    blockers=["Missing schema."],
                )
            ],
            execution_run={
                "run_id": "exec-run-test",
                "state": "interrupted",
                "target_workspace": str(tmp_path / "game"),
                "interrupted_reason": "process_lost",
            },
        )
    )
    persistence.append_event(
        {
            "event": "execution_interrupted_detected",
            "state": "executing",
            "workflow_id": "wf-interrupted",
            "data": {
                "run_id": "exec-run-test",
                "running_packages": ["WP-001"],
                "reason": "process_lost",
            },
            "timestamp": 1710000000.0,
        }
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    assert snapshot.execution_recovery is not None
    assert snapshot.target_workspace == str(tmp_path / "game")
    assert snapshot.execution_recovery.state == "interrupted"
    assert snapshot.execution_recovery.running_packages == ("WP-001",)
    assert snapshot.execution_recovery.retry_candidates == ("WP-001",)
    assert snapshot.execution_recovery.done_packages == ("WP-002",)
    assert snapshot.work_package_details[0].owner_agent == "codex"
    assert snapshot.work_package_details[0].current_executor == "claude"
    assert snapshot.work_package_details[0].risk == "high"
    assert snapshot.work_package_details[0].topic == "Shared contracts"
    assert snapshot.work_package_details[0].scope == ["Define API"]
    assert snapshot.work_package_details[0].expected_files == ["src/contracts.py"]
    assert snapshot.work_package_details[0].acceptance_criteria == ["Types compile"]
    assert snapshot.work_package_details[0].retryable is True
    assert snapshot.work_package_details[0].last_result_summary == "Could not finish."
    assert snapshot.work_package_details[0].last_result_blockers == ["Missing schema."]
    assert snapshot.work_package_details[1].retryable is False
    assert snapshot.work_package_details[1].retry_disabled_reason == "already done"


def test_snapshot_formats_legacy_execution_result_event(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-legacy-result",
            goal="Build game",
            state=WorkflowState.EXECUTING,
            active_agents=["codex"],
        )
    )
    persistence.append_event(
        {
            "event": "execution_result_recorded",
            "state": "executing",
            "workflow_id": "wf-legacy-result",
            "data": {
                "package_id": "WP-002",
                "agent": "codex",
                "status": "done",
            },
        }
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    assert snapshot.execution_log == ["work_package_completed: WP-002 codex done"]


def test_snapshot_hides_session_result_when_finished_event_is_visible(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-duplicate-result",
            goal="Build game",
            state=WorkflowState.EXECUTING,
            active_agents=["codex"],
            execution_results=[
                ExecutionResult(
                    package_id="WP-002",
                    agent_name="codex",
                    status=WorkStatus.DONE,
                    summary="Implemented storage.",
                )
            ],
        )
    )
    persistence.append_event(
        {
            "event": "work_package_completed",
            "state": "executing",
            "workflow_id": "wf-duplicate-result",
            "data": {
                "package_id": "WP-002",
                "agent": "codex",
                "status": "done",
                "summary": "Implemented storage.",
            },
        }
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    assert snapshot.execution_log == [
        "work_package_completed: WP-002 codex done - Implemented storage."
    ]


def test_snapshot_formats_execution_result_failure_reason(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-execution-result",
            goal="Build game",
            state=WorkflowState.FAILED,
            active_agents=["codex"],
            work_packages=[
                WorkPackage(
                    id="WP-004",
                    title="Enhancement tree",
                    owner_agent="codex",
                    objective="Build enhancement tree.",
                    status=WorkStatus.FAILED,
                )
            ],
            execution_results=[
                ExecutionResult(
                    package_id="WP-004",
                    agent_name="codex",
                    status=WorkStatus.FAILED,
                    summary="All execution attempts failed.",
                    blockers=[
                        (
                            "Not inside a trusted directory and "
                            "--skip-git-repo-check was not specified."
                        )
                    ],
                )
            ],
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    assert snapshot.execution_log == [
        (
            "WP-004 codex: failed - Not inside a trusted directory and "
            "--skip-git-repo-check was not specified."
        )
    ]


def test_snapshot_restores_provider_status_from_response_artifacts(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-artifacts",
            goal="Build UI",
            state=WorkflowState.NEEDS_USER_DECISION,
            active_agents=["claude"],
            current_round=1,
            created_at=0,
        )
    )
    response_dir = config.effective_state_dir / "responses" / "round-01"
    response_dir.mkdir(parents=True)
    clean_path = response_dir / "claude-round-1-claude-abc.clean.txt"
    raw_path = response_dir / "claude-round-1-claude-abc.raw.txt"
    clean_path.write_text("Use a compact dashboard.", encoding="utf-8")
    raw_path.write_text("RAW: Use a compact dashboard.", encoding="utf-8")
    os.utime(clean_path, (10, 10))
    os.utime(raw_path, (10, 10))

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    claude = snapshot.providers[0]
    assert claude.status == "Ready"
    assert claude.summary == "Use a compact dashboard."
    assert claude.raw_output == "RAW: Use a compact dashboard."


def test_snapshot_folds_recent_provider_events(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)

    snapshot = NexusSnapshotAdapter(config).load_snapshot(
        [
            TUIEvent(
                type=TUIEventType.AGENT_RESPONDED,
                data={"agent": "claude", "content": "Use a compact dashboard."},
            )
        ]
    )

    claude = snapshot.providers[0]
    assert claude.status == "Ready"
    assert claude.summary == "Use a compact dashboard."
    assert claude.raw_output == "Use a compact dashboard."


def test_snapshot_projects_active_round_and_synthesis_from_events(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-runtime",
            goal="Build game",
            state=WorkflowState.DELIBERATING,
            active_agents=["claude"],
            current_round=0,
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot(
        [
            TUIEvent(type=TUIEventType.ROUND_START, data={"round_num": 1}),
            TUIEvent(
                type=TUIEventType.AGENT_RESPONDED,
                data={
                    "agent": "claude",
                    "content": "Build a compact game.",
                    "round_num": 1,
                },
            ),
            TUIEvent(
                type=TUIEventType.CONSENSUS_CHECKING,
                data={"round_num": 1},
            ),
        ]
    )

    assert snapshot.round_num == 1
    assert snapshot.synthesis.status == "running"
    assert snapshot.synthesis.consensus_progress == "round 1 synthesizing"
    assert "Central agent is synthesizing round 1" in snapshot.synthesis.summary
    assert snapshot.providers[0].status == "Ready"


def test_snapshot_projects_consensus_result_from_events(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-runtime",
            goal="Build game",
            state=WorkflowState.DELIBERATING,
            active_agents=["claude"],
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot(
        [
            TUIEvent(
                type=TUIEventType.CONSENSUS_RESULT,
                data={
                    "round_num": 1,
                    "reached": False,
                    "agreement_count": 1,
                    "total_agents": 3,
                    "summary": "Need another round to resolve scope.",
                },
            )
        ]
    )

    assert snapshot.round_num == 1
    assert snapshot.synthesis.status == "ready"
    assert snapshot.synthesis.summary == "Need another round to resolve scope."
    assert snapshot.synthesis.consensus_progress == ("round 1 consensus not reached (1/3)")


def test_snapshot_projects_synthesis_fallback_reason_from_events(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-runtime",
            goal="Build game",
            state=WorkflowState.DELIBERATING,
            active_agents=["claude"],
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot(
        [
            TUIEvent(
                type=TUIEventType.CONSENSUS_RESULT,
                data={
                    "round_num": 1,
                    "reached": False,
                    "agreement_count": 0,
                    "total_agents": 3,
                    "summary": "No consensus yet.",
                    "synthesis_source": "heuristic",
                    "fallback_used": True,
                    "fallback_reason": "model synthesis provider returned timeout",
                },
            )
        ]
    )

    assert snapshot.synthesis.source == "heuristic"
    assert "fallback used" in snapshot.synthesis.consensus_progress
    assert "model synthesis provider returned timeout" in snapshot.synthesis.summary


def test_snapshot_projects_new_round_collection_after_previous_result(
    tmp_path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-runtime",
            goal="Build game",
            state=WorkflowState.DELIBERATING,
            active_agents=["claude"],
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot(
        [
            TUIEvent(
                type=TUIEventType.CONSENSUS_RESULT,
                data={
                    "round_num": 1,
                    "reached": False,
                    "agreement_count": 1,
                    "total_agents": 3,
                    "summary": "Need another round to resolve scope.",
                },
            ),
            TUIEvent(
                type=TUIEventType.ROUND_START,
                data={
                    "round_num": 2,
                },
            ),
        ]
    )

    assert snapshot.round_num == 2
    assert snapshot.synthesis.status == "waiting"
    assert snapshot.synthesis.consensus_progress == "round 2 collecting"
    assert snapshot.synthesis.summary == ("Collecting provider responses for round 2.")
