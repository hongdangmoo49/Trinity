from trinity.textual_app.execute_commands import (
    execute_result_presentation,
    execute_retry_no_packages_presentation,
    execution_recovery_snapshot,
)
from trinity.textual_app.snapshot import (
    ExecutionRecoverySnapshot,
    WorkflowNexusSnapshot,
)


def test_execute_result_presentation_skips_empty_message() -> None:
    assert execute_result_presentation(None) is None
    assert execute_result_presentation("") is None


def test_execute_result_presentation_wraps_message() -> None:
    presentation = execute_result_presentation("Finish planning before execution.")

    assert presentation is not None
    assert presentation.title == "Execute"
    assert presentation.body == "Finish planning before execution."
    assert presentation.severity == "warning"
    assert presentation.empty is True
    assert presentation.action_hint == (
        "Finish planning first, then run `/execute` from Nexus."
    )


def test_execute_retry_no_packages_presentation_uses_retry_copy() -> None:
    presentation = execute_retry_no_packages_presentation()

    assert presentation.title == "Execute Retry"
    assert presentation.body == (
        "No work packages are available in the current workflow."
    )
    assert presentation.severity == "warning"
    assert presentation.empty is True
    assert presentation.action_hint == (
        "Finish planning and execute at least one package first."
    )


def test_execute_retry_no_packages_presentation_supports_korean() -> None:
    presentation = execute_retry_no_packages_presentation(lang="ko")

    assert presentation.title == "실행 재시도"
    assert presentation.body == (
        "현재 워크플로우에 사용할 수 있는 작업 패키지가 없습니다."
    )
    assert presentation.action_hint == (
        "먼저 계획을 완료하고 하나 이상의 작업 패키지를 실행하세요."
    )


def test_execution_recovery_snapshot_builds_local_command_result() -> None:
    snapshot = WorkflowNexusSnapshot(
        execution_recovery=ExecutionRecoverySnapshot(
            run_id="run-1",
            state="blocked",
            target_workspace="/tmp/app",
            running_packages=("WP-1",),
            retry_candidates=("WP-1",),
            done_packages=("WP-0",),
            last_event="provider failed",
        )
    )

    result = execution_recovery_snapshot(
        "/execute",
        snapshot,
        "Execution interrupted.",
    )

    assert result.command == "/execute"
    assert result.title == "Execution Recovery"
    assert result.body.startswith("Execution interrupted.")
    assert "- Execution: `blocked`" in result.body
    assert result.severity == "warning"
    assert result.action_hint == (
        "Use `/execute-retry`, `/execute mark-interrupted`, or `/execute abort`."
    )
    assert result.table_columns == ("Item", "Value")
    assert ("Run", "run-1") in result.table_rows
    assert ("Retry candidates", "WP-1") in result.table_rows


def test_execution_recovery_snapshot_supports_korean_title() -> None:
    snapshot = WorkflowNexusSnapshot(
        execution_recovery=ExecutionRecoverySnapshot(run_id="run-1")
    )

    result = execution_recovery_snapshot("/execute", snapshot, lang="ko")

    assert result.title == "실행 복구"
    assert result.table_columns == ("항목", "값")
