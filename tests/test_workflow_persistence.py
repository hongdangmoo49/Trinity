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
