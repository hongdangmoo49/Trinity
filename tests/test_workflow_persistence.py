"""Tests for workflow persistence helpers."""

from trinity.workflow import (
    AgentRuntimeModel,
    Blueprint,
    ProviderSessionRef,
    WorkPackage,
    WorkflowPersistence,
    WorkflowSession,
    WorkflowState,
)


def test_workflow_persistence_round_trips_typed_blueprint(tmp_path):
    persistence = WorkflowPersistence(tmp_path / ".trinity")
    session = WorkflowSession(
        id="wf-test",
        goal="Design",
        state=WorkflowState.BLUEPRINT_READY,
        blueprint=Blueprint(
            title="Route Bot",
            summary="Find bridge routes.",
            data_flow=["request -> route"],
        ),
    )

    persistence.save(session)
    loaded = persistence.load()

    assert loaded is not None
    assert loaded.id == "wf-test"
    assert loaded.blueprint is not None
    assert loaded.blueprint.title == "Route Bot"
    assert loaded.blueprint.data_flow == ["request -> route"]


def test_workflow_persistence_round_trips_work_package_repair_notes(tmp_path):
    persistence = WorkflowPersistence(tmp_path / ".trinity")
    session = WorkflowSession(
        id="wf-repairs",
        goal="Implement",
        state=WorkflowState.BLUEPRINT_READY,
        work_packages=[
            WorkPackage(
                id="WP-001",
                title="Shared setup",
                owner_agent="codex",
                objective="Prepare shared setup.",
                repair_notes=[
                    "owner reassigned from 'missing' to 'codex'",
                    "expected_files missing; using unknown write scope",
                ],
            )
        ],
    )

    persistence.save(session)
    loaded = persistence.load()

    assert loaded is not None
    assert loaded.work_packages[0].repair_notes == [
        "owner reassigned from 'missing' to 'codex'",
        "expected_files missing; using unknown write scope",
    ]


def test_workflow_persistence_round_trips_provider_metadata(tmp_path):
    persistence = WorkflowPersistence(tmp_path / ".trinity")
    session = WorkflowSession(
        id="wf-provider",
        goal="Design",
        state=WorkflowState.DELIBERATING,
        provider_sessions={
            "codex:key": ProviderSessionRef(
                provider="codex",
                agent_name="codex",
                session_key="codex:key",
                provider_session_id="thread-1",
                session_kind="codex_thread",
                access="read-only",
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

    persistence.save(session)
    loaded = persistence.load()

    assert loaded is not None
    assert loaded.provider_sessions["codex:key"].provider_session_id == "thread-1"
    assert loaded.runtime_models["codex"].actual_model == "gpt-5.5"
    assert loaded.runtime_models["codex"].context_window == 272000


def test_workflow_persistence_appends_and_loads_events(tmp_path):
    persistence = WorkflowPersistence(tmp_path / ".trinity")
    persistence.append_event(
        {
            "timestamp": 1.0,
            "workflow_id": "wf-test",
            "event": "state_changed",
            "state": "deliberating",
            "data": {"reason": "test"},
        }
    )

    assert persistence.load_events() == [
        {
            "timestamp": 1.0,
            "workflow_id": "wf-test",
            "event": "state_changed",
            "state": "deliberating",
            "data": {"reason": "test"},
        }
    ]

    persistence.clear()
    assert persistence.load() is None
    assert persistence.load_events() == []


def test_workflow_persistence_loads_events_for_one_workflow(tmp_path):
    persistence = WorkflowPersistence(tmp_path / ".trinity")
    persistence.append_event({"event": "started", "workflow_id": "wf-a"})
    persistence.append_event({"event": "ignored", "workflow_id": "wf-b"})
    persistence.append_event({"event": "completed", "workflow_id": "wf-a"})
    persistence.append_event({"event": "state_changed", "workflow_id": "wf-a"})

    assert persistence.load_events_for_workflow("wf-a", tail=2) == [
        {"event": "completed", "workflow_id": "wf-a"},
        {"event": "state_changed", "workflow_id": "wf-a"},
    ]
    assert persistence.load_events_for_workflow(
        "wf-a",
        event_names={"completed"},
    ) == [{"event": "completed", "workflow_id": "wf-a"}]
    assert persistence.last_event_for_workflow("wf-a") == {
        "event": "state_changed",
        "workflow_id": "wf-a",
    }


def test_workflow_persistence_archives_and_restores_active_session(tmp_path):
    persistence = WorkflowPersistence(tmp_path / ".trinity")
    session = WorkflowSession(
        id="wf-archive",
        goal="Keep whale tracker design",
        state=WorkflowState.FAILED,
    )
    persistence.save(session)
    persistence.append_event({"event": "failed", "workflow_id": "wf-archive"})

    archive = persistence.archive_active_session()

    assert archive is not None
    assert archive.session.id == "wf-archive"
    assert persistence.load() is None
    assert persistence.load_events() == []

    archives = persistence.list_archives()
    assert len(archives) == 1
    restored = persistence.restore_archive(archives[0])

    assert restored.id == "wf-archive"
    assert persistence.load() is not None
    assert persistence.load().goal == "Keep whale tracker design"
    assert persistence.load_events() == [{"event": "failed", "workflow_id": "wf-archive"}]


def test_workflow_persistence_does_not_archive_empty_idle_session(tmp_path):
    persistence = WorkflowPersistence(tmp_path / ".trinity")
    persistence.save(WorkflowSession(id="wf-idle", goal="", state=WorkflowState.IDLE))

    archive = persistence.archive_active_session()

    assert archive is None
    assert persistence.load() is None
    assert persistence.list_archives() == []
