from trinity.textual_app.snapshot import QuestionSnapshot, WorkflowNexusSnapshot
from trinity.textual_app.workflow_commands import workflow_command_presentation


def test_workflow_command_presentation_marks_new_workflow_snapshot() -> None:
    presentation = workflow_command_presentation(WorkflowNexusSnapshot())

    assert presentation.title == "Workflow"
    assert "- ID: `(new)`" in presentation.body
    assert "- Goal: (none)" in presentation.body
    assert presentation.table_columns == ("Item", "Value")
    assert ("ID", "(new)") in presentation.table_rows
    assert ("Goal", "(none)") in presentation.table_rows


def test_workflow_command_presentation_includes_workflow_counts() -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-1",
        goal="Ship",
        state="planning",
        round_num=2,
        questions=[QuestionSnapshot(id="q1", question="Continue?")],
        decisions=["Go"],
        work_packages=["WP-001 codex: build"],
        subtasks=[],
        execution_log=["WP-001 done"],
    )

    presentation = workflow_command_presentation(snapshot)

    assert presentation.title == "Workflow"
    assert "- ID: `wf-1`" in presentation.body
    assert "- Pending questions: `1`" in presentation.body
    assert "- Decisions: `1`" in presentation.body
    assert "- Work Packages: `1`" in presentation.body
    assert ("Execution log entries", "1") in presentation.table_rows


def test_workflow_command_presentation_uses_korean_labels() -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-ko",
        goal="배포",
        state="planning",
        round_num=2,
        questions=[QuestionSnapshot(id="q1", question="진행할까요?")],
        decisions=["진행"],
    )

    presentation = workflow_command_presentation(snapshot, lang="ko")

    assert presentation.title == "워크플로우"
    assert "- 목표: 배포" in presentation.body
    assert "- 대기 중 질문: `1`" in presentation.body
    assert "- 결정: `1`" in presentation.body
    assert presentation.table_columns == ("항목", "값")
    assert ("목표", "배포") in presentation.table_rows
