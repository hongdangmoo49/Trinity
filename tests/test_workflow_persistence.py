"""Tests for workflow persistence helpers."""

import json
import logging
from pathlib import Path

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
    assert persistence.event_index_path.exists()


def test_workflow_persistence_uses_event_index_for_workflow_filter(tmp_path, monkeypatch):
    persistence = WorkflowPersistence(tmp_path / ".trinity")
    persistence.append_event({"event": "started", "workflow_id": "wf-a"})
    persistence.append_event({"event": "ignored", "workflow_id": "wf-b"})
    persistence.append_event({"event": "completed", "workflow_id": "wf-a"})

    def fail_full_scan():
        raise AssertionError("load_events should not run when event index is valid")

    monkeypatch.setattr(persistence, "load_events", fail_full_scan)

    assert persistence.load_events_for_workflow("wf-a", tail=1) == [
        {"event": "completed", "workflow_id": "wf-a"}
    ]


def test_workflow_persistence_caches_event_index_until_file_changes(
    tmp_path,
    monkeypatch,
):
    persistence = WorkflowPersistence(tmp_path / ".trinity")
    persistence.append_event({"event": "started", "workflow_id": "wf-a"})
    persistence.append_event({"event": "ignored", "workflow_id": "wf-b"})
    persistence.append_event({"event": "completed", "workflow_id": "wf-a"})

    read_count = 0
    original_open = Path.open

    def counted_open(path, *args, **kwargs):
        nonlocal read_count
        mode = args[0] if args else kwargs.get("mode", "r")
        if path == persistence.event_index_path and "r" in str(mode):
            read_count += 1
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", counted_open)

    assert persistence.load_events_for_workflow("wf-a", tail=1) == [
        {"event": "completed", "workflow_id": "wf-a"}
    ]
    assert read_count == 1

    assert persistence.load_events_for_workflow("wf-a", tail=1) == [
        {"event": "completed", "workflow_id": "wf-a"}
    ]
    assert read_count == 1

    persistence.append_event({"event": "state_changed", "workflow_id": "wf-a"})
    assert persistence.load_events_for_workflow("wf-a", tail=1) == [
        {"event": "state_changed", "workflow_id": "wf-a"}
    ]
    assert read_count == 2


def test_workflow_persistence_returns_empty_events_without_live_log(tmp_path, caplog):
    persistence = WorkflowPersistence(tmp_path / ".trinity")
    caplog.set_level(logging.ERROR, logger="trinity.workflow.persistence")

    assert persistence.load_events_for_workflow("wf-missing") == []
    assert "Failed to load workflow events from index" not in caplog.text


def test_workflow_persistence_ignores_index_when_live_log_was_removed(tmp_path, caplog):
    persistence = WorkflowPersistence(tmp_path / ".trinity")
    persistence.append_event({"event": "started", "workflow_id": "wf-a"})
    persistence.events_path.unlink()
    caplog.set_level(logging.ERROR, logger="trinity.workflow.persistence")

    assert persistence.load_events_for_workflow("wf-a") == []
    assert "Failed to load workflow events from index" not in caplog.text


def test_workflow_persistence_rebuilds_stale_event_index(tmp_path):
    persistence = WorkflowPersistence(tmp_path / ".trinity")
    persistence.append_event({"event": "started", "workflow_id": "wf-a"})
    persistence.event_index_path.write_text(
        json.dumps(
            {
                "version": 1,
                "events_size_bytes": 0,
                "events_mtime_ns": 0,
                "workflows": {},
            }
        ),
        encoding="utf-8",
    )

    assert persistence.load_events_for_workflow("wf-a") == [
        {"event": "started", "workflow_id": "wf-a"}
    ]
    index_lines = [
        json.loads(line)
        for line in persistence.event_index_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(item["workflow_id"] == "wf-a" for item in index_lines)


def test_workflow_persistence_caches_events_until_file_changes(tmp_path, monkeypatch):
    persistence = WorkflowPersistence(tmp_path / ".trinity")
    persistence.append_event({"event": "started", "workflow_id": "wf-a"})

    read_count = 0
    original_open = Path.open

    def counted_open(path, *args, **kwargs):
        nonlocal read_count
        mode = args[0] if args else kwargs.get("mode", "r")
        if path == persistence.events_path and "r" in str(mode):
            read_count += 1
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", counted_open)

    first = persistence.load_events()
    assert first == [{"event": "started", "workflow_id": "wf-a"}]
    assert read_count == 1

    first[0]["event"] = "mutated"
    assert persistence.load_events() == [{"event": "started", "workflow_id": "wf-a"}]
    assert read_count == 1

    persistence.append_event({"event": "completed", "workflow_id": "wf-a"})
    assert persistence.load_events() == [
        {"event": "started", "workflow_id": "wf-a"},
        {"event": "completed", "workflow_id": "wf-a"},
    ]
    assert read_count == 2


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


def test_workflow_persistence_lists_archives_from_manifest(tmp_path, monkeypatch):
    persistence = WorkflowPersistence(tmp_path / ".trinity")
    for index in range(3):
        persistence.save(
            WorkflowSession(
                id=f"wf-{index}",
                goal=f"Goal {index}",
                state=WorkflowState.BLUEPRINT_READY,
                updated_at=float(index),
            )
        )
        assert persistence.archive_active_session(force=True) is not None

    assert persistence.archive_manifest_path.exists()
    archive_json_paths = {
        path
        for path in persistence.history_dir.glob("*.json")
        if path != persistence.archive_manifest_path
    }
    original_read_text = Path.read_text

    def guarded_read_text(path, *args, **kwargs):
        if path in archive_json_paths:
            raise AssertionError(f"archive JSON should not be read: {path}")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    archives = persistence.list_archives()

    assert [archive.session.id for archive in archives] == ["wf-2", "wf-1", "wf-0"]
    assert [archive.session.goal for archive in archives] == ["Goal 2", "Goal 1", "Goal 0"]


def test_workflow_persistence_rebuilds_stale_archive_manifest(tmp_path):
    persistence = WorkflowPersistence(tmp_path / ".trinity")
    persistence.save(
        WorkflowSession(
            id="wf-original",
            goal="Original",
            state=WorkflowState.DONE,
            updated_at=1.0,
        )
    )
    assert persistence.archive_active_session(force=True) is not None
    persistence.archive_manifest_path.write_text(
        json.dumps({"version": 1, "archives": []}),
        encoding="utf-8",
    )

    archives = persistence.list_archives()

    assert [archive.session.id for archive in archives] == ["wf-original"]
    manifest = json.loads(persistence.archive_manifest_path.read_text(encoding="utf-8"))
    assert manifest["archives"][0]["id"] == "wf-original"
