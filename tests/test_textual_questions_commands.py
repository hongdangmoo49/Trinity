from trinity.textual_app.questions_commands import (
    questions_command_presentation,
    questions_command_presentation_from_args,
    questions_select_requested,
)
from trinity.textual_app.snapshot import QuestionSnapshot, WorkflowNexusSnapshot


def test_questions_command_presentation_marks_empty_questions() -> None:
    presentation = questions_command_presentation(WorkflowNexusSnapshot())

    assert presentation.title == "Questions"
    assert presentation.empty is True
    assert presentation.body == "No pending workflow questions."
    assert presentation.action_hint == (
        "Continue planning until the central agent raises a question."
    )
    assert presentation.table_columns == ("ID", "Status", "Question", "Options")
    assert presentation.table_rows == ()


def test_questions_command_presentation_includes_question_rows() -> None:
    snapshot = WorkflowNexusSnapshot(
        questions=[
            QuestionSnapshot(
                id="q-1",
                question="Choose a theme?",
                options=["dark", "light"],
            )
        ]
    )

    presentation = questions_command_presentation(snapshot)

    assert presentation.empty is False
    assert presentation.action_hint.startswith("Use question panel buttons")
    assert "1. **q-1** [open] Choose a theme?" in presentation.body
    assert presentation.table_rows == (
        ("q-1", "open", "Choose a theme?", "dark, light"),
    )


def test_questions_command_presentation_uses_select_body() -> None:
    snapshot = WorkflowNexusSnapshot(
        questions=[
            QuestionSnapshot(
                id="q-1",
                question="Choose a theme?",
                options=["dark", "light"],
            )
        ]
    )

    presentation = questions_command_presentation(snapshot, select_requested=True)

    assert "Selected question: **q-1**" in presentation.body
    assert "Use the option buttons in the question panel" in presentation.body


def test_questions_select_requested_recognizes_flags() -> None:
    assert questions_select_requested(["--select"]) is True
    assert questions_select_requested(["-S"]) is True
    assert questions_select_requested(["all"]) is False


def test_questions_command_presentation_from_args_uses_select_flag() -> None:
    snapshot = WorkflowNexusSnapshot(
        questions=[
            QuestionSnapshot(
                id="q-1",
                question="Choose a theme?",
                options=["dark", "light"],
            )
        ]
    )

    presentation = questions_command_presentation_from_args(["-s"], snapshot)

    assert "Selected question: **q-1**" in presentation.body


def test_questions_command_presentation_uses_korean_labels() -> None:
    snapshot = WorkflowNexusSnapshot(
        questions=[
            QuestionSnapshot(
                id="q-1",
                question="테마를 선택할까요?",
                options=["dark", "light"],
            )
        ]
    )

    presentation = questions_command_presentation(
        snapshot,
        select_requested=True,
        lang="ko",
    )

    assert presentation.title == "질문"
    assert presentation.empty is False
    assert "선택된 질문: **q-1**" in presentation.body
    assert presentation.table_columns == ("ID", "상태", "질문", "선택지")
    assert presentation.table_rows == (
        ("q-1", "열림", "테마를 선택할까요?", "dark, light"),
    )
