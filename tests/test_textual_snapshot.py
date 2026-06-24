from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from trinity.config import TrinityConfig
from trinity.context.shared import SharedContextEngine
from trinity.textual_app.snapshot import (
    NexusSnapshotAdapter,
    WORKFLOW_EVENT_DISPLAY_LIMIT,
)
from trinity.tui.events import TUIEvent, TUIEventType
from trinity.workflow import (
    AgentRuntimeModel,
    Blueprint,
    ExecutionResult,
    OpenQuestion,
    PostReviewActionItem,
    PostReviewActionStatus,
    ProviderSessionRef,
    WorkflowPersistence,
    ReviewDepth,
    ReviewPackage,
    ReviewResult,
    ReviewStatus,
    WorkflowSession,
    WorkflowState,
    WorkPackage,
    WorkStatus,
    DecisionRecord,
)
from trinity.workflow.persistence import WorkflowEventSlice


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
    assert snapshot.providers[0].context_profile == "architect"
    assert "architecture" in snapshot.providers[0].profile_strengths[0]


def test_snapshot_marks_non_ok_provider_response_event_as_error(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)

    snapshot = NexusSnapshotAdapter(config).load_snapshot(
        [
            TUIEvent(
                type=TUIEventType.AGENT_RESPONDED,
                data={
                    "agent": "claude",
                    "content": "[Error: exit code 1]",
                    "response_status": "auth_required",
                },
            )
        ]
    )

    claude = next(provider for provider in snapshot.providers if provider.name == "claude")
    assert claude.status == "Error"
    assert claude.response_status == "auth_required"
    assert claude.summary == "[Error: exit code 1]"


def test_snapshot_projects_provider_output_contract_from_runtime_event(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)

    snapshot = NexusSnapshotAdapter(config).load_snapshot(
        [
            TUIEvent(
                type=TUIEventType.WORK_PACKAGE_STARTED,
                data={
                    "agent": "codex",
                    "package_id": "WP-001",
                    "status": "running",
                    "output_contract": "execution_v1",
                },
            ),
            TUIEvent(
                type=TUIEventType.REVIEW_PACKAGE_STARTED,
                data={
                    "reviewer_agent": "antigravity",
                    "review_package_id": "RP-WP-001-antigravity",
                    "package_id": "WP-001",
                    "status": "reviewing",
                    "output_contract": "review_v1",
                },
            ),
        ]
    )

    by_name = {provider.name: provider for provider in snapshot.providers}
    assert by_name["codex"].output_contract == "execution_v1"
    assert by_name["antigravity"].output_contract == "review_v1"


def test_snapshot_marks_non_ok_persisted_response_artifact_as_error(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-provider-error",
            goal="Build UI",
            state=WorkflowState.BLUEPRINT_READY,
            active_agents=["claude"],
            current_round=1,
        )
    )
    clean_path = config.effective_state_dir / "responses" / "round-01" / "claude-r1.clean.txt"
    raw_path = config.effective_state_dir / "responses" / "round-01" / "claude-r1.raw.txt"
    clean_path.parent.mkdir(parents=True, exist_ok=True)
    clean_path.write_text("[Error: exit code 1]", encoding="utf-8")
    raw_path.write_text("provider stderr", encoding="utf-8")
    SharedContextEngine(config.shared_context_path).append_response_reference(
        agent="claude",
        round_num=1,
        request_id="r1",
        status="invalid",
        clean_output_path=clean_path,
        raw_output_path=raw_path,
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    claude = next(provider for provider in snapshot.providers if provider.name == "claude")
    assert claude.status == "Error"
    assert claude.response_status == "invalid"
    assert claude.summary == "[Error: exit code 1]"
    assert claude.raw_output == ""
    assert claude.raw_output_path == str(raw_path)


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


def test_snapshot_projects_work_package_routing_metadata(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-routing",
            goal="Build routing",
            state=WorkflowState.BLUEPRINT_READY,
            active_agents=["codex"],
            work_packages=[
                WorkPackage(
                    id="WP-001",
                    title="Routing",
                    owner_agent="codex",
                    objective="Implement routing.",
                    task_kind="implementation",
                    routing_reason="implementation strength 0.95",
                    routing_score=111.0,
                    profile_revision="default-v1",
                )
            ],
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    package = snapshot.work_package_details[0]
    assert package.task_kind == "implementation"
    assert package.routing_reason == "implementation strength 0.95"
    assert package.routing_score == 111.0
    assert package.profile_revision == "default-v1"


def test_snapshot_marks_non_target_agents_idle_during_targeted_deliberation(
    tmp_path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents["codex"].enabled = True
    config.agents["antigravity"].enabled = True
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-targeted",
            goal="Ask codex only",
            state=WorkflowState.DELIBERATING,
            active_agents=["claude", "codex", "antigravity"],
            last_target_agents=["codex"],
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()
    by_name = {provider.name: provider for provider in snapshot.providers}

    assert by_name["codex"].status == "Running"
    assert by_name["claude"].status == "Idle"
    assert by_name["antigravity"].status == "Idle"


def test_snapshot_uses_event_index_without_full_event_projection_read(
    tmp_path,
    monkeypatch,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-events",
            goal="Build UI",
            state=WorkflowState.EXECUTING,
            work_packages=[
                WorkPackage(
                    id="WP-001",
                    title="Frontend shell",
                    owner_agent="codex",
                    objective="Build the frontend shell.",
                    status=WorkStatus.RUNNING,
                )
            ],
            execution_run={"state": "running", "run_id": "run-1"},
        )
    )
    persistence.append_event(
        {"event": "execution_run_started", "workflow_id": "wf-events"}
    )
    persistence.append_event(
        {"event": "work_package_started", "workflow_id": "wf-events"}
    )
    persistence.append_event(
        {"event": "ignored", "workflow_id": "wf-other"}
    )

    adapter = NexusSnapshotAdapter(config)
    calls = 0
    original_load_events = adapter.persistence.load_events

    def counted_load_events():
        nonlocal calls
        calls += 1
        return original_load_events()

    monkeypatch.setattr(adapter.persistence, "load_events", counted_load_events)

    snapshot = adapter.load_snapshot()

    assert calls == 0
    assert snapshot.execution_recovery is not None
    assert snapshot.execution_recovery.last_event == "work_package_started"
    assert snapshot.workflow_events == [
        "execution_run_started: 0 packages",
        "work_package_started",
    ]
    assert snapshot.execution_log == [
        "execution_run_started: 0 packages",
        "work_package_started",
    ]


def test_snapshot_large_event_log_uses_event_index_and_tail_limit(
    tmp_path,
    monkeypatch,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-large",
            goal="Build UI",
            state=WorkflowState.EXECUTING,
            work_packages=[
                WorkPackage(
                    id=f"WP-{index:03d}",
                    title=f"Package {index}",
                    owner_agent="codex",
                    objective=f"Build package {index}.",
                    status=WorkStatus.RUNNING if index == 1 else WorkStatus.DONE,
                )
                for index in range(1, 101)
            ],
            execution_run={"state": "running", "run_id": "run-large"},
        )
    )
    for index in range(5_000):
        persistence.append_event(
            {
                "event": "work_package_started",
                "workflow_id": "wf-large",
                "data": {"package_id": f"WP-{index % 100:03d}", "agent": "codex"},
            }
        )
    persistence.append_event(
        {"event": "ignored", "workflow_id": "wf-other"}
    )

    adapter = NexusSnapshotAdapter(config)
    calls = 0
    original_load_events = adapter.persistence.load_events

    def counted_load_events():
        nonlocal calls
        calls += 1
        return original_load_events()

    monkeypatch.setattr(adapter.persistence, "load_events", counted_load_events)

    snapshot = adapter.load_snapshot()

    assert calls == 0
    assert len(snapshot.execution_log) == 80
    assert len(snapshot.workflow_events) == 501
    assert snapshot.workflow_events[0] == "... 4500 older workflow events omitted"
    assert snapshot.execution_recovery is not None
    assert snapshot.execution_recovery.last_event == "work_package_started"
    assert snapshot.execution_recovery.retry_candidates == ("WP-001",)


def test_snapshot_fallback_helpers_use_bounded_event_loads(
    tmp_path,
    monkeypatch,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    adapter = NexusSnapshotAdapter(config)
    session = WorkflowSession(
        id="wf-fallback",
        goal="Build UI",
        state=WorkflowState.EXECUTING,
    )
    event_tail = [
        {
            "event": "work_package_started",
            "workflow_id": "wf-fallback",
            "data": {"package_id": "WP-2", "agent": "codex"},
        },
        {
            "event": "work_package_completed",
            "workflow_id": "wf-fallback",
            "data": {"package_id": "WP-2", "agent": "codex"},
        },
    ]
    load_event_tails: list[int | None] = []
    slice_tails: list[int | None] = []

    def fake_load_events_for_workflow(
        workflow_id: str,
        *,
        tail: int | None = None,
        event_names=None,
    ):
        assert workflow_id == "wf-fallback"
        load_event_tails.append(tail)
        return event_tail[-1:] if tail == 1 else list(event_tail)

    def fake_load_event_slice_for_workflow(
        workflow_id: str,
        *,
        tail: int | None = None,
        event_names=None,
    ):
        assert workflow_id == "wf-fallback"
        slice_tails.append(tail)
        return WorkflowEventSlice(events=list(event_tail), total=3)

    monkeypatch.setattr(
        adapter.persistence,
        "load_events_for_workflow",
        fake_load_events_for_workflow,
    )
    monkeypatch.setattr(
        adapter.persistence,
        "load_event_slice_for_workflow",
        fake_load_event_slice_for_workflow,
    )

    assert adapter._execution_log(session) == [
        "work_package_started: WP-2 codex",
        "work_package_completed: WP-2 codex",
    ]
    assert adapter._workflow_events(session) == [
        "... 1 older workflow events omitted",
        "work_package_started: WP-2 codex",
        "work_package_completed: WP-2 codex",
    ]
    assert adapter._last_session_event(session) == event_tail[-1]
    assert load_event_tails == [80, 1]
    assert slice_tails == [WORKFLOW_EVENT_DISPLAY_LIMIT]


def test_snapshot_reuses_cached_projection_until_events_change(
    tmp_path,
    monkeypatch,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-cache",
            goal="Build cache",
            state=WorkflowState.EXECUTING,
            active_agents=["claude", "codex"],
        )
    )

    adapter = NexusSnapshotAdapter(config)
    load_calls = 0
    original_load = adapter.persistence.load

    def counted_load():
        nonlocal load_calls
        load_calls += 1
        return original_load()

    monkeypatch.setattr(adapter.persistence, "load", counted_load)

    first = adapter.load_snapshot()
    second = adapter.load_snapshot()

    assert second is first
    assert load_calls == 1

    persistence.append_event(
        {
            "event": "work_package_started",
            "workflow_id": "wf-cache",
            "data": {"package_id": "WP-001", "agent": "codex"},
        }
    )

    third = adapter.load_snapshot()

    assert third is not first
    assert load_calls == 2
    assert third.workflow_events == ["work_package_started: WP-001 codex"]


def test_snapshot_cache_key_includes_recent_events(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    adapter = NexusSnapshotAdapter(config)

    first_event = [
        TUIEvent(
            type=TUIEventType.AGENT_RESPONDED,
            data={"agent": "claude", "content": "First runtime summary."},
        )
    ]
    second_event = [
        TUIEvent(
            type=TUIEventType.AGENT_RESPONDED,
            data={"agent": "claude", "content": "Second runtime summary."},
        )
    ]

    first = adapter.load_snapshot(first_event)
    second = adapter.load_snapshot(first_event)
    third = adapter.load_snapshot(second_event)

    assert second is first
    assert third is not first
    assert third.providers[0].summary == "Second runtime summary."


def test_snapshot_cache_invalidates_when_shared_context_changes(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-shared-cache",
            goal="Use shared context",
            state=WorkflowState.NEEDS_USER_DECISION,
            active_agents=["claude"],
        )
    )
    shared = SharedContextEngine(config.shared_context_path)
    shared.update_consensus("First agreed conclusion.")

    adapter = NexusSnapshotAdapter(config)
    first = adapter.load_snapshot()
    shared.update_consensus("Second agreed conclusion.")
    second = adapter.load_snapshot()

    assert second is not first
    assert first.synthesis.summary == "First agreed conclusion."
    assert second.synthesis.summary == "Second agreed conclusion."


def test_snapshot_projects_provider_runtime_metadata(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-provider",
            goal="Build UI",
            state=WorkflowState.DELIBERATING,
            active_agents=["codex"],
            provider_sessions={
                "codex:key": ProviderSessionRef(
                    provider="codex",
                    agent_name="codex",
                    session_key="codex:key",
                    provider_session_id="019ea9e3-426f",
                    session_kind="codex_thread",
                    access="read-only",
                    last_observed_at=2.0,
                )
            },
            runtime_models={
                "codex": AgentRuntimeModel(
                    provider="codex",
                    agent_name="codex",
                    configured_model="default",
                    actual_model="gpt-5.5",
                    context_window=272000,
                    budget_source="local_cli_cache",
                    confidence="medium-high",
                )
            },
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()
    codex = next(provider for provider in snapshot.providers if provider.name == "codex")

    assert codex.provider == "codex · gpt-5.5"
    assert codex.actual_model == "gpt-5.5"
    assert codex.context_window == 272000
    assert codex.budget_source == "local_cli_cache"
    assert codex.session_id == "019ea9e3-426f"


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


def test_snapshot_projects_work_package_and_final_review_results(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-review",
            goal="Build UI",
            state=WorkflowState.REVIEWING,
            active_agents=["claude", "codex"],
            work_packages=[
                WorkPackage(
                    id="WP-001",
                    title="Frontend shell",
                    owner_agent="claude",
                    objective="Build the shell.",
                    status=WorkStatus.DONE,
                )
            ],
            review_results=[
                ReviewResult(
                    review_package_id="RP-WP-001-codex",
                    package_id="WP-001",
                    reviewer_agent="codex",
                    target_agent="claude",
                    status=ReviewStatus.CHANGES_REQUESTED,
                    severity="high",
                    summary="Needs safer terminal handling.",
                    required_changes=["Add resize regression test."],
                    performance_notes=["Rendering remains bounded."],
                ).to_dict(),
                ReviewResult(
                    review_package_id="RP-FINAL-codex",
                    package_id="FINAL",
                    reviewer_agent="codex",
                    target_agent="project",
                    status=ReviewStatus.APPROVED,
                    severity="low",
                    scope="final",
                    summary="Project is coherent and runnable.",
                    compatibility_notes=["Textual UI remains compatible."],
                ).to_dict(),
            ],
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    package = snapshot.work_package_details[0]
    assert package.review_status == "changes_requested"
    assert package.reviewer_agent == "codex"
    assert package.review_severity == "high"
    assert package.review_required_changes == ["Add resize regression test."]
    assert snapshot.final_review is not None
    assert snapshot.final_review.status == "approved"
    assert snapshot.final_review.summary == "Project is coherent and runnable."
    assert snapshot.final_review.compatibility_notes == ["Textual UI remains compatible."]


def test_snapshot_projects_planned_review_as_reviewing(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-reviewing",
            goal="Build UI",
            state=WorkflowState.REVIEWING,
            active_agents=["claude", "codex", "antigravity"],
            work_packages=[
                WorkPackage(
                    id="WP-001",
                    title="Frontend shell",
                    owner_agent="claude",
                    objective="Build the shell.",
                    status=WorkStatus.DONE,
                )
            ],
            review_packages=[
                ReviewPackage(
                    id="RP-WP-001-codex",
                    package_id="WP-001",
                    reviewer_agent="codex",
                    target_agent="claude",
                ).to_dict(),
                ReviewPackage(
                    id="RP-WP-001-antigravity",
                    package_id="WP-001",
                    reviewer_agent="antigravity",
                    target_agent="claude",
                ).to_dict(),
            ],
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    package = snapshot.work_package_details[0]
    assert package.review_status == "reviewing"
    assert package.reviewer_agent == "codex, antigravity"


def test_snapshot_projects_planned_review_as_queued_before_reviewing(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-review-queued",
            goal="Build UI",
            state=WorkflowState.EXECUTING,
            active_agents=["claude", "codex"],
            work_packages=[
                WorkPackage(
                    id="WP-001",
                    title="Frontend shell",
                    owner_agent="claude",
                    objective="Build the shell.",
                    status=WorkStatus.DONE,
                )
            ],
            review_packages=[
                ReviewPackage(
                    id="RP-WP-001-codex",
                    package_id="WP-001",
                    reviewer_agent="codex",
                    target_agent="claude",
                ).to_dict()
            ],
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    assert snapshot.work_package_details[0].review_status == "queued"


def test_snapshot_projects_single_provider_review_skip_reason(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-review-skipped",
            goal="Build UI",
            state=WorkflowState.REVIEWING,
            active_agents=["codex"],
            work_packages=[
                WorkPackage(
                    id="WP-001",
                    title="CLI fallback",
                    owner_agent="codex",
                    objective="Build the fallback.",
                    status=WorkStatus.DONE,
                )
            ],
            review_packages=[
                ReviewPackage(
                    id="RP-WP-001-skipped-no-peer",
                    package_id="WP-001",
                    reviewer_agent="",
                    target_agent="codex",
                    depth=ReviewDepth.NONE,
                    required=False,
                    skipped_reason=(
                        "only codex is active; no non-owner peer reviewer is available"
                    ),
                ).to_dict()
            ],
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    package = snapshot.work_package_details[0]
    assert package.review_status == "skipped"
    assert package.reviewer_agent == ""
    assert (
        package.review_summary
        == "only codex is active; no non-owner peer reviewer is available"
    )


def test_snapshot_folds_runtime_review_started_over_queued_plan(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-review-runtime-started",
            goal="Build UI",
            state=WorkflowState.EXECUTING,
            active_agents=["claude", "codex"],
            work_packages=[
                WorkPackage(
                    id="WP-001",
                    title="Frontend shell",
                    owner_agent="claude",
                    objective="Build the shell.",
                    status=WorkStatus.DONE,
                )
            ],
            review_packages=[
                ReviewPackage(
                    id="RP-WP-001-codex",
                    package_id="WP-001",
                    reviewer_agent="codex",
                    target_agent="claude",
                ).to_dict()
            ],
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot(
        [
            TUIEvent(
                type=TUIEventType.REVIEW_PACKAGE_STARTED,
                data={
                    "review_package_id": "RP-WP-001-codex",
                    "package_id": "WP-001",
                    "reviewer_agent": "codex",
                    "target_agent": "claude",
                    "status": "reviewing",
                },
            )
        ]
    )

    package = snapshot.work_package_details[0]
    assert package.review_status == "reviewing"
    assert package.reviewer_agent == "codex"


def test_snapshot_folds_runtime_review_completed_before_persisted_result(
    tmp_path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-review-runtime-completed",
            goal="Build UI",
            state=WorkflowState.REVIEWING,
            active_agents=["claude", "codex"],
            work_packages=[
                WorkPackage(
                    id="WP-001",
                    title="Frontend shell",
                    owner_agent="claude",
                    objective="Build the shell.",
                    status=WorkStatus.DONE,
                )
            ],
            review_packages=[
                ReviewPackage(
                    id="RP-WP-001-codex",
                    package_id="WP-001",
                    reviewer_agent="codex",
                    target_agent="claude",
                ).to_dict()
            ],
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot(
        [
            TUIEvent(
                type=TUIEventType.REVIEW_PACKAGE_COMPLETED,
                data={
                    "review_package_id": "RP-WP-001-codex",
                    "package_id": "WP-001",
                    "reviewer_agent": "codex",
                    "target_agent": "claude",
                    "status": ReviewStatus.CHANGES_REQUESTED.value,
                    "severity": "high",
                    "summary": "Needs safer terminal handling.",
                    "required_changes": ["Add resize regression test."],
                },
            )
        ]
    )

    package = snapshot.work_package_details[0]
    assert package.review_status == "changes_requested"
    assert package.reviewer_agent == "codex"
    assert package.review_summary == "Needs safer terminal handling."
    assert package.review_required_changes == ["Add resize regression test."]
    assert package.review_severity == "high"


def test_snapshot_runtime_review_started_overrides_stale_persisted_result(
    tmp_path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-review-runtime-rerun",
            goal="Build UI",
            state=WorkflowState.REVIEWING,
            active_agents=["claude", "codex"],
            work_packages=[
                WorkPackage(
                    id="WP-001",
                    title="Frontend shell",
                    owner_agent="claude",
                    objective="Build the shell.",
                    status=WorkStatus.DONE,
                )
            ],
            review_packages=[
                ReviewPackage(
                    id="RP-WP-001-codex",
                    package_id="WP-001",
                    reviewer_agent="codex",
                    target_agent="claude",
                ).to_dict()
            ],
            review_results=[
                ReviewResult(
                    review_package_id="RP-WP-001-codex",
                    package_id="WP-001",
                    reviewer_agent="codex",
                    target_agent="claude",
                    status=ReviewStatus.APPROVED,
                    severity="low",
                    summary="Previous review passed.",
                ).to_dict()
            ],
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot(
        [
            TUIEvent(
                type=TUIEventType.REVIEW_PACKAGE_STARTED,
                data={
                    "review_package_id": "RP-WP-001-codex",
                    "package_id": "WP-001",
                    "reviewer_agent": "codex",
                    "target_agent": "claude",
                    "status": "reviewing",
                },
            )
        ]
    )

    package = snapshot.work_package_details[0]
    assert package.review_status == "reviewing"
    assert package.review_summary == ""


def test_snapshot_aggregates_multiple_work_package_review_results(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-review-aggregate",
            goal="Build UI",
            state=WorkflowState.REVIEWING,
            active_agents=["claude", "codex", "antigravity"],
            work_packages=[
                WorkPackage(
                    id="WP-001",
                    title="Frontend shell",
                    owner_agent="claude",
                    objective="Build the shell.",
                    status=WorkStatus.DONE,
                )
            ],
            review_packages=[
                ReviewPackage(
                    id="RP-WP-001-codex",
                    package_id="WP-001",
                    reviewer_agent="codex",
                    target_agent="claude",
                ).to_dict(),
                ReviewPackage(
                    id="RP-WP-001-antigravity",
                    package_id="WP-001",
                    reviewer_agent="antigravity",
                    target_agent="claude",
                ).to_dict(),
            ],
            review_results=[
                ReviewResult(
                    review_package_id="RP-WP-001-codex",
                    package_id="WP-001",
                    reviewer_agent="codex",
                    target_agent="claude",
                    status=ReviewStatus.APPROVED,
                    severity="low",
                    summary="Looks good.",
                ).to_dict(),
                ReviewResult(
                    review_package_id="RP-WP-001-antigravity",
                    package_id="WP-001",
                    reviewer_agent="antigravity",
                    target_agent="claude",
                    status=ReviewStatus.CHANGES_REQUESTED,
                    severity="critical",
                    summary="Needs a terminal resize fix.",
                    required_changes=["Add resize regression test."],
                ).to_dict(),
            ],
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    package = snapshot.work_package_details[0]
    assert package.review_status == "changes_requested"
    assert package.reviewer_agent == "codex, antigravity"
    assert package.review_summary == "Needs a terminal resize fix."
    assert package.review_required_changes == ["Add resize regression test."]
    assert package.review_severity == "critical"


def test_snapshot_marks_pending_escalated_review_as_needs_second_review(
    tmp_path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    primary = ReviewPackage(
        id="RP-WP-001-codex",
        package_id="WP-001",
        reviewer_agent="codex",
        target_agent="claude",
    )
    persistence.save(
        WorkflowSession(
            id="wf-review-escalated-pending",
            goal="Build UI",
            state=WorkflowState.REVIEWING,
            active_agents=["claude", "codex", "antigravity"],
            work_packages=[
                WorkPackage(
                    id="WP-001",
                    title="Frontend shell",
                    owner_agent="claude",
                    objective="Build the shell.",
                    status=WorkStatus.DONE,
                )
            ],
            review_packages=[
                primary.to_dict(),
                ReviewPackage(
                    id="RP-WP-001-antigravity",
                    package_id="WP-001",
                    reviewer_agent="antigravity",
                    target_agent="claude",
                    depth=ReviewDepth.ESCALATED_PEER,
                    escalation_parent_id=primary.id,
                    reason="primary review status is changes_requested",
                ).to_dict(),
            ],
            review_results=[
                ReviewResult(
                    review_package_id=primary.id,
                    package_id="WP-001",
                    reviewer_agent="codex",
                    target_agent="claude",
                    status=ReviewStatus.CHANGES_REQUESTED,
                    severity="high",
                    summary="Needs a second look.",
                    required_changes=["Check terminal resize handling."],
                ).to_dict()
            ],
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    package = snapshot.work_package_details[0]
    assert package.review_status == "needs_second_review"
    assert package.reviewer_agent == "codex, antigravity"
    assert package.review_summary == "Needs a second look."
    assert package.review_required_changes == ["Check terminal resize handling."]
    assert package.review_severity == "high"


def test_snapshot_reuses_review_index_for_package_and_final_review(
    tmp_path,
    monkeypatch,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-review-index",
            goal="Build UI",
            state=WorkflowState.REVIEWING,
            work_packages=[
                WorkPackage(
                    id="WP-001",
                    title="Frontend shell",
                    owner_agent="claude",
                    objective="Build the shell.",
                    status=WorkStatus.DONE,
                )
            ],
            review_results=[
                ReviewResult(
                    review_package_id="RP-WP-001-codex",
                    package_id="WP-001",
                    reviewer_agent="codex",
                    target_agent="claude",
                    status=ReviewStatus.CHANGES_REQUESTED,
                    summary="Needs resize handling.",
                ).to_dict(),
                ReviewResult(
                    review_package_id="RP-FINAL-codex",
                    package_id="FINAL",
                    reviewer_agent="codex",
                    target_agent="all",
                    status=ReviewStatus.APPROVED,
                    scope="final",
                    summary="Project is coherent.",
                ).to_dict(),
            ],
        )
    )
    calls = 0
    original = NexusSnapshotAdapter._review_results

    def counted(session):
        nonlocal calls
        calls += 1
        return original(session)

    monkeypatch.setattr(NexusSnapshotAdapter, "_review_results", staticmethod(counted))

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    assert calls == 1
    assert snapshot.work_package_details[0].review_status == "changes_requested"
    assert snapshot.final_review is not None
    assert snapshot.final_review.summary == "Project is coherent."


def test_snapshot_projects_post_review_follow_up_items(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-post-review",
            goal="Build UI",
            state=WorkflowState.POST_REVIEW_READY,
            active_agents=["claude"],
            post_review_items=[
                PostReviewActionItem(
                    id="AI-001",
                    source="final_review",
                    kind="test",
                    severity="high",
                    title="Add regression tests",
                    summary="Add final review regression tests.",
                    suggested_owner="claude",
                    status=PostReviewActionStatus.PROPOSED,
                    related_wp_ids=["WP-001"],
                ).to_dict()
            ],
            follow_up_requests=[
                {
                    "id": "fur-001",
                    "text": "/improve high",
                    "source_state": "post_review_ready",
                    "accepted_action_item_ids": ["AI-001"],
                }
            ],
            supplemental_round=1,
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    assert snapshot.state == "post_review_ready"
    assert snapshot.supplemental_round == 1
    assert len(snapshot.post_review_items) == 1
    item = snapshot.post_review_items[0]
    assert item.id == "AI-001"
    assert item.status == "proposed"
    assert item.related_wp_ids == ("WP-001",)
    assert snapshot.follow_up_requests == ["fur-001: /improve high"]


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
                    attempt_chain=[
                        {
                            "agent": "codex",
                            "status": "blocked",
                            "summary": "Owner could not continue.",
                            "blockers": ["Missing schema."],
                            "raw_response_path": "/tmp/codex.raw.txt",
                        },
                        {
                            "agent": "claude",
                            "status": "failed",
                            "summary": "Could not finish.",
                            "blockers": ["Missing schema."],
                            "raw_response_path": "/tmp/claude.raw.txt",
                        },
                    ],
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
    assert snapshot.work_package_details[0].last_result_attempt_chain == [
        (
            "1. `codex` `blocked` - Owner could not continue. "
            "(blockers: Missing schema.) [raw: /tmp/codex.raw.txt]"
        ),
        (
            "2. `claude` `failed` - Could not finish. "
            "(blockers: Missing schema.) [raw: /tmp/claude.raw.txt]"
        ),
    ]
    assert snapshot.work_package_details[1].retryable is False
    assert snapshot.work_package_details[1].retry_disabled_reason == "already done"


def test_snapshot_projects_failed_execution_recovery(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    target = tmp_path / "game"
    persistence.save(
        WorkflowSession(
            id="wf-failed-execution",
            goal="Build game",
            state=WorkflowState.FAILED,
            active_agents=["claude"],
            target_workspace=target,
            work_packages=[
                WorkPackage(
                    id="WP-001",
                    title="client",
                    owner_agent="claude",
                    objective="Build client.",
                    status=WorkStatus.FAILED,
                    last_executor="claude",
                )
            ],
            execution_run={
                "run_id": "exec-run-failed",
                "state": "failed",
                "outcome": "failed",
                "target_workspace": str(target),
            },
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    assert snapshot.execution_recovery is not None
    assert snapshot.execution_recovery.state == "failed"
    assert snapshot.execution_recovery.retry_candidates == ("WP-001",)


def test_snapshot_projects_review_repair_blocked_state(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    notes = [f"repair note {index}" for index in range(10)]
    persistence.save(
        WorkflowSession(
            id="wf-repair-blocked",
            goal="Build game",
            state=WorkflowState.NEEDS_USER_DECISION,
            active_agents=["codex", "claude"],
            target_workspace=tmp_path / "game",
            work_packages=[
                WorkPackage(
                    id="WP-001",
                    title="Client",
                    owner_agent="codex",
                    objective="Build client.",
                    status=WorkStatus.BLOCKED,
                    repair_notes=notes,
                    repair_attempt_count=3,
                    last_repair_signature="sig-1",
                    last_repair_review_id="RP-WP-001-claude",
                    repair_blocked_reason="duplicate_required_changes",
                    repair_blocked_at=123.5,
                )
            ],
            execution_run={
                "run_id": "exec-run-repair",
                "state": "repair_blocked",
                "target_workspace": str(tmp_path / "game"),
                "repair_blocked_packages": ["WP-001"],
            },
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    assert snapshot.execution_recovery is not None
    assert snapshot.execution_recovery.state == "repair_blocked"
    assert snapshot.execution_recovery.retry_candidates == ("WP-001",)
    assert snapshot.work_packages == [
        "WP-001 codex: Client (blocked) repair 3/3 blocked: duplicate_required_changes"
    ]
    package = snapshot.work_package_details[0]
    assert package.repair_attempt_count == 3
    assert package.repair_max_attempts == config.repair_max_attempts
    assert package.repair_blocked_reason == "duplicate_required_changes"
    assert package.repair_blocked_at == 123.5
    assert package.retryable is True
    assert snapshot.work_package_repairs == [
        "WP-001: repair note 3",
        "WP-001: repair note 4",
        "WP-001: repair note 5",
        "WP-001: repair note 6",
        "WP-001: repair note 7",
        "WP-001: repair note 8",
        "WP-001: repair note 9",
        "WP-001: blocked after 3 repair attempts (duplicate_required_changes)",
    ]


def test_snapshot_projects_mixed_review_repair_retry_and_blocked_state(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-mixed-repair",
            goal="Build game",
            state=WorkflowState.BLUEPRINT_READY,
            active_agents=["codex", "claude"],
            target_workspace=tmp_path / "game",
            work_packages=[
                WorkPackage(
                    id="WP-001",
                    title="Retry package",
                    owner_agent="codex",
                    objective="Retry.",
                    status=WorkStatus.PENDING,
                    repair_attempt_count=1,
                    last_repair_signature="sig-retry",
                ),
                WorkPackage(
                    id="WP-002",
                    title="Blocked package",
                    owner_agent="claude",
                    objective="Blocked.",
                    status=WorkStatus.BLOCKED,
                    repair_attempt_count=3,
                    last_repair_signature="sig-blocked",
                    repair_blocked_reason="max_attempts_exceeded",
                ),
            ],
            execution_run={
                "run_id": "exec-run-mixed",
                "state": "retry_requested",
                "target_workspace": str(tmp_path / "game"),
                "retry_selector": "review-repair",
                "retry_packages": ["WP-001"],
                "repair_blocked_packages": ["WP-002"],
            },
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    assert snapshot.execution_recovery is None
    assert snapshot.work_packages == [
        "WP-001 codex: Retry package (pending) repair 1/3",
        "WP-002 claude: Blocked package (blocked) repair 3/3 blocked: max_attempts_exceeded",
    ]
    assert snapshot.work_package_repairs == [
        "WP-002: blocked after 3 repair attempts (max_attempts_exceeded)"
    ]
    assert snapshot.work_package_details[0].repair_attempt_count == 1
    assert snapshot.work_package_details[1].repair_blocked_reason == "max_attempts_exceeded"


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
    assert claude.raw_output == ""
    assert claude.raw_output_path == str(raw_path)


def test_snapshot_reads_only_bounded_artifact_preview(tmp_path, monkeypatch) -> None:
    read_sizes: list[int] = []

    class FakeArtifact:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, size: int = -1) -> bytes:
            read_sizes.append(size)
            return b"x" * size

    def fake_open(path, *args, **kwargs):
        return FakeArtifact()

    monkeypatch.setattr(Path, "open", fake_open)

    text = NexusSnapshotAdapter._read_artifact_text(tmp_path / "large.raw.txt", limit=5)

    assert read_sizes == [6]
    assert text == "xxxxx\n..."


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
