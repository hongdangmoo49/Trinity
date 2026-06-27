from trinity.textual_app.local_commands import (
    append_local_command_event,
    local_command_result_effect,
    local_command_notification,
    local_command_snapshot,
    recent_local_command_results,
    replace_local_command_result,
    snapshot_with_local_command_results,
)
from trinity.textual_app.snapshot import LocalCommandSnapshot, WorkflowNexusSnapshot
from trinity.workflow import WorkflowPersistence, WorkflowSession, WorkflowState


def _result(command: str, title: str = "Title") -> LocalCommandSnapshot:
    return LocalCommandSnapshot(command=command, title=title, body="Body")


def test_local_command_snapshot_builds_result_payload() -> None:
    result = local_command_snapshot(
        "/status",
        "Status",
        "Ready.",
        severity="warning",
        empty=True,
        action_hint="Check providers.",
        table_columns=("Field", "Value"),
        table_rows=(("State", "ready"),),
    )

    assert result.command == "/status"
    assert result.title == "Status"
    assert result.body == "Ready."
    assert result.severity == "warning"
    assert result.empty is True
    assert result.action_hint == "Check providers."
    assert result.table_columns == ("Field", "Value")
    assert result.table_rows == (("State", "ready"),)


def test_local_command_notification_maps_severity_and_title() -> None:
    notification = local_command_notification(
        _result("/status", "Status"),
        lang="en",
    )

    assert notification.message == "Status"
    assert notification.title == "Slash Command"
    assert notification.severity == "information"


def test_local_command_notification_warns_for_warning_result_and_localizes() -> None:
    notification = local_command_notification(
        LocalCommandSnapshot(
            command="/status",
            title="상태",
            body="주의",
            severity="warning",
        ),
        lang="ko",
    )

    assert notification.message == "상태"
    assert notification.title == "슬래시 명령"
    assert notification.severity == "warning"


def test_replace_local_command_result_keeps_latest_per_command() -> None:
    results = [_result("/status", "Old"), _result("/workflow")]

    updated = replace_local_command_result(results, _result("/status", "New"))

    assert [item.command for item in updated] == ["/workflow", "/status"]
    assert updated[-1].title == "New"


def test_recent_local_command_results_is_bounded() -> None:
    results = [_result(f"/cmd-{index}") for index in range(10)]

    recent = recent_local_command_results(results, limit=3)

    assert [item.command for item in recent] == ["/cmd-7", "/cmd-8", "/cmd-9"]
    assert recent_local_command_results(results, limit=0) == []


def test_snapshot_with_local_command_results_attaches_recent_results() -> None:
    snapshot = WorkflowNexusSnapshot(session_id="wf-local")
    results = [_result(f"/cmd-{index}") for index in range(4)]

    updated = snapshot_with_local_command_results(snapshot, results, limit=2)

    assert updated.session_id == "wf-local"
    assert [item.command for item in updated.local_commands] == ["/cmd-2", "/cmd-3"]
    assert snapshot.local_commands == []


def test_local_command_result_effect_shows_start_modal() -> None:
    result = _result("/status", "Status")

    effect = local_command_result_effect(
        result,
        WorkflowNexusSnapshot(session_id="wf-local"),
        [],
        current_route="start",
    )

    assert effect.show_modal is True
    assert effect.modal_result is result
    assert effect.notification is None
    assert effect.local_command_results == [result]
    assert effect.snapshot.local_commands == [result]


def test_local_command_result_effect_updates_route_and_notifies() -> None:
    result = _result("/status", "Status")

    effect = local_command_result_effect(
        result,
        WorkflowNexusSnapshot(session_id="wf-local"),
        [],
        current_route="nexus",
    )

    assert effect.show_modal is False
    assert effect.modal_result is None
    assert effect.notification is not None
    assert effect.notification.message == "Status"
    assert effect.notification.title == "Slash Command"
    assert effect.snapshot.local_commands == [result]


def test_local_command_result_effect_can_skip_notification() -> None:
    result = _result("/status", "Status")

    effect = local_command_result_effect(
        result,
        WorkflowNexusSnapshot(session_id="wf-local"),
        [],
        current_route="nexus",
        notify=False,
    )

    assert effect.notification is None
    assert effect.snapshot.local_commands == [result]


def test_local_command_result_effect_replaces_previous_result() -> None:
    old = _result("/status", "Old")
    result = _result("/status", "New")

    effect = local_command_result_effect(
        result,
        WorkflowNexusSnapshot(session_id="wf-local"),
        [old, _result("/workflow")],
        current_route="nexus",
    )

    assert [item.command for item in effect.local_command_results] == [
        "/workflow",
        "/status",
    ]
    assert effect.local_command_results[-1].title == "New"
    assert [item.command for item in effect.snapshot.local_commands] == [
        "/workflow",
        "/status",
    ]


def test_append_local_command_event_records_reportable_conversation(tmp_path) -> None:
    persistence = WorkflowPersistence(tmp_path)
    persistence.save(
        WorkflowSession(
            id="wf-local",
            goal="test local command persistence",
            state=WorkflowState.BLUEPRINT_READY,
        )
    )

    recorded = append_local_command_event(
        tmp_path,
        _result("/status", "Status"),
        timestamp=12.345,
    )

    events = persistence.load_events_for_workflow("wf-local")
    assert recorded is True
    assert events[-1]["event"] == "central_conversation_recorded"
    assert events[-1]["timestamp"] == 12.345
    assert events[-1]["state"] == "blueprint_ready"
    assert events[-1]["data"]["message_id"] == "cc-local-12345"
    assert events[-1]["data"]["channel"] == "local_command"
    assert events[-1]["data"]["command"] == "/status"


def test_append_local_command_event_skips_without_session(tmp_path) -> None:
    result = append_local_command_event(tmp_path, _result("/status"), timestamp=1.0)

    assert result is False
    assert WorkflowPersistence(tmp_path).load_events() == []
