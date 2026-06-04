"""Tests for workflow persistence helpers."""

from trinity.workflow import Blueprint, WorkflowPersistence, WorkflowSession, WorkflowState


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
