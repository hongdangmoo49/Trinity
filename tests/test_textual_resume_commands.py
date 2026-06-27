from types import SimpleNamespace

from trinity.textual_app.resume_commands import (
    resume_archives_presentation,
    resume_cancelled_presentation,
    resume_no_saved_presentation,
    resume_result_command_presentation,
    resume_result_presentation,
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
