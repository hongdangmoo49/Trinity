from trinity.textual_app.decisions_commands import decisions_command_presentation
from trinity.textual_app.snapshot import WorkflowNexusSnapshot


def test_decisions_command_presentation_marks_empty_decisions() -> None:
    presentation = decisions_command_presentation(WorkflowNexusSnapshot())

    assert presentation.title == "Decisions"
    assert presentation.empty is True
    assert presentation.body == "No workflow decisions recorded in the current session."
    assert presentation.action_hint == (
        "Answer pending questions with `/answer` to add decisions."
    )
    assert presentation.table_columns == ("#", "Decision")
    assert presentation.table_rows == ()


def test_decisions_command_presentation_includes_decision_rows() -> None:
    snapshot = WorkflowNexusSnapshot(decisions=["Use dark theme", "Ship MVP"])

    presentation = decisions_command_presentation(snapshot)

    assert presentation.empty is False
    assert presentation.action_hint == ""
    assert presentation.body == "1. Use dark theme\n2. Ship MVP"
    assert presentation.table_rows == (
        ("1", "Use dark theme"),
        ("2", "Ship MVP"),
    )


def test_decisions_command_presentation_uses_korean_labels() -> None:
    snapshot = WorkflowNexusSnapshot(decisions=["다크 테마 사용"])

    presentation = decisions_command_presentation(snapshot, lang="ko")

    assert presentation.title == "결정"
    assert presentation.empty is False
    assert presentation.body == "1. 다크 테마 사용"
    assert presentation.action_hint == ""
    assert presentation.table_columns == ("#", "결정")
    assert presentation.table_rows == (("1", "다크 테마 사용"),)
