from trinity.textual_app.history_commands import history_command_presentation
from trinity.textual_app.snapshot import LocalCommandSnapshot, WorkflowNexusSnapshot


def test_history_command_presentation_marks_empty_history() -> None:
    presentation = history_command_presentation(WorkflowNexusSnapshot(), [])

    assert presentation.title == "History"
    assert presentation.empty is True
    assert presentation.action_hint == (
        "Run a prompt, execute a workflow, or use local slash commands first."
    )
    assert presentation.table_columns == ("Kind", "Item")
    assert presentation.table_rows == ()


def test_history_command_presentation_includes_local_command_history() -> None:
    result = LocalCommandSnapshot(
        command="/status",
        title="Status",
        body="ok",
    )

    presentation = history_command_presentation(WorkflowNexusSnapshot(), [result])

    assert presentation.empty is False
    assert presentation.action_hint == ""
    assert presentation.table_rows
    assert any("/status" in row[1] for row in presentation.table_rows)


def test_history_command_presentation_uses_korean_labels() -> None:
    result = LocalCommandSnapshot(
        command="/status",
        title="상태",
        body="정상",
    )

    presentation = history_command_presentation(
        WorkflowNexusSnapshot(),
        [result],
        lang="ko",
    )

    assert presentation.title == "워크플로우 이력"
    assert presentation.table_columns == ("종류", "항목")
    assert presentation.empty is False
