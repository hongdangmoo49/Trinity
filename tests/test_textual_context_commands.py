from trinity.textual_app.context_commands import (
    context_command_presentation,
    context_command_snapshot_update,
)
from trinity.textual_app.snapshot import SynthesisSnapshot, WorkflowNexusSnapshot


def test_context_command_presentation_notifies_on_empty_start_route() -> None:
    presentation = context_command_presentation(
        "/context",
        WorkflowNexusSnapshot(),
        route="start",
    )

    assert presentation.action == "notify"
    assert presentation.title == "Context"
    assert "No current session context" in presentation.body
    assert presentation.severity == "warning"
    assert presentation.result is None


def test_context_command_presentation_records_empty_nexus_context() -> None:
    presentation = context_command_presentation(
        "/context",
        WorkflowNexusSnapshot(),
        route="nexus",
        lang="ko",
    )

    assert presentation.action == "record"
    assert presentation.title == "컨텍스트"
    assert presentation.body == (
        "현재 세션 컨텍스트가 없습니다. 먼저 프롬프트를 시작하거나 워크플로우를 재개하세요."
    )
    assert presentation.severity == "info"
    assert presentation.result is None


def test_context_command_presentation_opens_modal_on_start_with_context() -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-1",
        goal="Build",
        synthesis=SynthesisSnapshot(summary="Ready"),
    )

    presentation = context_command_presentation("/context", snapshot, route="start")

    assert presentation.action == "modal"
    assert presentation.result is not None
    assert presentation.result.command == "/context"
    assert "Build" in presentation.result.body


def test_context_command_presentation_applies_snapshot_off_start_route() -> None:
    snapshot = WorkflowNexusSnapshot(session_id="wf-1", goal="Build")

    presentation = context_command_presentation("/context", snapshot, route="nexus")

    assert presentation.action == "apply_snapshot"
    assert presentation.result is not None
    assert presentation.result.title == "Context"
    assert "- Workflow: `wf-1`" in presentation.result.body


def test_context_command_snapshot_update_skips_without_result() -> None:
    presentation = context_command_presentation(
        "/context",
        WorkflowNexusSnapshot(),
        route="nexus",
    )

    assert context_command_snapshot_update(
        presentation,
        WorkflowNexusSnapshot(),
        [],
    ) is None


def test_context_command_snapshot_update_replaces_context_result() -> None:
    first_snapshot = WorkflowNexusSnapshot(session_id="wf-1", goal="First")
    first = context_command_presentation(
        "/context",
        first_snapshot,
        route="nexus",
    )
    assert first.result is not None
    second_snapshot = WorkflowNexusSnapshot(session_id="wf-2", goal="Second")
    second = context_command_presentation(
        "/context",
        second_snapshot,
        route="nexus",
    )
    assert second.result is not None

    first_update = context_command_snapshot_update(first, first_snapshot, [])
    assert first_update is not None
    second_update = context_command_snapshot_update(
        second,
        second_snapshot,
        first_update.local_command_results,
    )

    assert second_update is not None
    assert second_update.local_command_results == [second.result]
    assert second_update.result is second.result
    assert second_update.snapshot.local_commands == [second.result]
