from types import SimpleNamespace

from trinity.textual_app.resume_commands import (
    resume_command_action,
    resume_archives_presentation,
    resume_cancelled_presentation,
    resume_no_saved_presentation,
    resume_result_command_presentation,
    resume_result_presentation,
    resume_workflow_effect,
    should_continue_resumed_workflow,
)
from trinity.textual_app.snapshot import WorkflowNexusSnapshot


def test_resume_result_presentation_skips_empty_message() -> None:
    assert resume_result_presentation(None) is None
    assert resume_result_presentation("") is None


def test_resume_result_presentation_marks_no_message_as_failure() -> None:
    presentation = resume_result_presentation("No saved workflow found.")

    assert presentation is not None
    assert presentation.failed is True
    assert presentation.severity == "warning"
    assert presentation.empty is True
    assert presentation.start_modal is True
    assert should_continue_resumed_workflow(presentation) is False


def test_resume_result_presentation_keeps_info_message_continuable() -> None:
    presentation = resume_result_presentation("Resumed workflow wf-1.")

    assert presentation is not None
    assert presentation.failed is False
    assert presentation.severity == "info"
    assert presentation.empty is False
    assert presentation.start_modal is False
    assert should_continue_resumed_workflow(presentation) is True


def test_should_continue_resumed_workflow_without_message() -> None:
    assert should_continue_resumed_workflow(None) is True


def test_resume_no_saved_presentation_describes_empty_state() -> None:
    presentation = resume_no_saved_presentation()

    assert presentation.title == "Resume"
    assert presentation.body == "No saved workflow sessions to resume."
    assert presentation.empty is True
    assert presentation.action_hint == (
        "Start and archive a workflow before using `/resume`."
    )


def test_resume_archives_presentation_lists_archive_choices() -> None:
    archives = [
        SimpleNamespace(
            selector="1",
            session_id="wf-1",
            state="paused",
            goal="ship it",
        )
    ]

    presentation = resume_archives_presentation(archives)

    assert presentation.title == "Resume"
    assert presentation.body == (
        "Saved workflow sessions available to resume.\n"
        "- `1` wf-1 [paused] ship it"
    )
    assert presentation.table_columns == ("Selector", "Workflow", "State", "Goal")
    assert presentation.table_rows == (("1", "wf-1", "paused", "ship it"),)
    assert presentation.action_hint == "Pick a workflow from the resume modal."
    assert presentation.start_modal is False


def test_resume_command_action_records_no_saved_workflows() -> None:
    action = resume_command_action([], [], lang="ko")

    assert action.kind == "record"
    assert action.selector == ""
    assert action.archives == ()
    assert action.presentation is not None
    assert action.presentation.title == "재개"
    assert action.presentation.empty is True


def test_resume_command_action_opens_picker_for_archives() -> None:
    archive = SimpleNamespace(
        selector="1",
        session_id="wf-1",
        state="paused",
        goal="ship it",
    )

    action = resume_command_action([], [archive])

    assert action.kind == "picker"
    assert action.selector == ""
    assert action.archives == (archive,)
    assert action.presentation is not None
    assert action.presentation.start_modal is False
    assert action.presentation.table_rows == (("1", "wf-1", "paused", "ship it"),)


def test_resume_command_action_routes_explicit_selector_without_listing() -> None:
    action = resume_command_action(["latest"], [])

    assert action.kind == "resume"
    assert action.selector == "latest"
    assert action.archives == ()
    assert action.presentation is None


def test_resume_cancelled_presentation_uses_korean_labels() -> None:
    presentation = resume_cancelled_presentation(lang="ko")

    assert presentation.title == "재개"
    assert presentation.body == "재개 선택을 취소했습니다."
    assert presentation.empty is True
    assert presentation.action_hint == (
        "보관된 워크플로우를 선택하려면 `/resume`을 다시 실행하세요."
    )


def test_resume_result_command_presentation_builds_result_rows() -> None:
    result = resume_result_presentation("Resumed workflow wf-1.")
    assert result is not None
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-1",
        state="running",
        goal="ship it",
        round_num=2,
    )

    presentation = resume_result_command_presentation(result, snapshot)

    assert presentation.title == "Resume"
    assert presentation.body == "Resumed workflow wf-1."
    assert presentation.severity == "info"
    assert presentation.empty is False
    assert presentation.table_columns == ("Item", "Value")
    assert presentation.table_rows == (
        ("Workflow", "wf-1"),
        ("State", "running"),
        ("Goal", "ship it"),
        ("Round", "2"),
    )
    assert presentation.start_modal is False


def test_resume_workflow_effect_stops_on_failed_resume_message() -> None:
    snapshot = WorkflowNexusSnapshot(session_id="wf-1", state="idle")
    outcome = SimpleNamespace(snapshot=snapshot, execution_recovery_required=False)

    effect = resume_workflow_effect(outcome, "No saved workflow found.")

    assert effect.presentation is not None
    assert effect.presentation.severity == "warning"
    assert effect.switch_to_nexus is False
    assert effect.execution_recovery_snapshot is None
    assert effect.show_context is False


def test_resume_workflow_effect_continues_without_message() -> None:
    snapshot = WorkflowNexusSnapshot(session_id="wf-1", state="running")
    outcome = SimpleNamespace(snapshot=snapshot, execution_recovery_required=False)

    effect = resume_workflow_effect(outcome, None)

    assert effect.presentation is None
    assert effect.switch_to_nexus is True
    assert effect.execution_recovery_snapshot is None
    assert effect.show_context is True


def test_resume_workflow_effect_marks_execution_recovery() -> None:
    snapshot = WorkflowNexusSnapshot(session_id="wf-1", state="running")
    outcome = SimpleNamespace(snapshot=snapshot, execution_recovery_required=True)

    effect = resume_workflow_effect(outcome, "Resumed workflow wf-1.")

    assert effect.presentation is not None
    assert effect.presentation.severity == "info"
    assert effect.switch_to_nexus is True
    assert effect.execution_recovery_snapshot is snapshot
    assert "Previous execution was interrupted" in effect.execution_recovery_message
    assert effect.show_context is True
