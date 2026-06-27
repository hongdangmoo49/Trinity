from trinity.textual_app.snapshot import SubtaskSnapshot, WorkflowNexusSnapshot
from trinity.textual_app.subtasks_commands import subtasks_command_presentation


def test_subtasks_command_presentation_marks_empty_subtasks() -> None:
    presentation = subtasks_command_presentation(WorkflowNexusSnapshot())

    assert presentation.title == "Subtasks"
    assert presentation.empty is True
    assert presentation.body == (
        "No provider delegation subtasks recorded in the current session."
    )
    assert presentation.action_hint == (
        "Subtasks appear after an executing provider reports delegated work."
    )
    assert presentation.table_columns == (
        "ID",
        "Package",
        "Delegated To",
        "Status",
        "Summary",
    )
    assert presentation.table_rows == ()


def test_subtasks_command_presentation_includes_subtask_rows() -> None:
    snapshot = WorkflowNexusSnapshot(
        subtasks=[
            SubtaskSnapshot(
                id="ST-001",
                parent_package_id="WP-001",
                parent_agent="claude",
                delegated_to="codex",
                objective="Build feature",
                result_summary="Done",
                status="done",
            )
        ]
    )

    presentation = subtasks_command_presentation(snapshot)

    assert presentation.empty is False
    assert presentation.action_hint == ""
    assert presentation.body == "1. **ST-001** [done] WP-001 -> codex: Done"
    assert presentation.table_rows == (
        ("ST-001", "WP-001", "codex", "done", "Done"),
    )


def test_subtasks_command_presentation_uses_korean_labels() -> None:
    snapshot = WorkflowNexusSnapshot(
        subtasks=[
            SubtaskSnapshot(
                id="",
                parent_package_id="",
                parent_agent="",
                delegated_to="",
                objective="구현",
                result_summary="",
                status="waiting",
            )
        ]
    )

    presentation = subtasks_command_presentation(snapshot, lang="ko")

    assert presentation.title == "하위 작업"
    assert presentation.empty is False
    assert presentation.body == "1. **(이름 없음)** [대기] (패키지 없음) -> (알 수 없음): 구현"
    assert presentation.table_columns == (
        "ID",
        "작업 패키지",
        "위임 대상",
        "상태",
        "요약",
    )
    assert presentation.table_rows == (
        ("(이름 없음)", "(없음)", "(알 수 없음)", "대기", "구현"),
    )
