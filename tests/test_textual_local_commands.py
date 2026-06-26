from trinity.textual_app.local_commands import (
    recent_local_command_results,
    replace_local_command_result,
    snapshot_with_local_command_results,
)
from trinity.textual_app.snapshot import LocalCommandSnapshot, WorkflowNexusSnapshot


def _result(command: str, title: str = "Title") -> LocalCommandSnapshot:
    return LocalCommandSnapshot(command=command, title=title, body="Body")


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
