from types import SimpleNamespace

from trinity.textual_app.execute_commands import (
    execute_command_effect,
    execute_result_presentation,
    execute_retry_no_packages_presentation,
    execution_retry_request_effect,
    execution_recovery_snapshot,
    run_execute_command,
)
from trinity.textual_app.snapshot import (
    ExecutionRecoverySnapshot,
    WorkPackageSnapshot,
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
        "Prepare work packages, then run `/execute` from Nexus."
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
        "Prepare and execute at least one package first."
    )


def test_execute_retry_no_packages_presentation_supports_korean() -> None:
    presentation = execute_retry_no_packages_presentation(lang="ko")

    assert presentation.title == "실행 재시도"
    assert presentation.body == (
        "현재 워크플로우에 사용할 수 있는 작업 패키지가 없습니다."
    )
    assert presentation.action_hint == (
        "하나 이상의 작업 패키지를 준비하고 실행하세요."
    )


def test_execution_retry_request_effect_warns_without_work_packages() -> None:
    snapshot = WorkflowNexusSnapshot(session_id="wf-1")

    effect = execution_retry_request_effect(
        snapshot,
        "failed",
        ("WP-1",),
        lang="ko",
    )

    assert effect.snapshot is snapshot
    assert effect.selector == "failed"
    assert effect.package_ids == ("WP-1",)
    assert effect.show_retry_modal is False
    assert effect.no_packages_presentation is not None
    assert effect.no_packages_presentation.title == "실행 재시도"


def test_execution_retry_request_effect_opens_modal_with_packages() -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-1",
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-1",
                title="Build",
                owner_agent="codex",
                status="failed",
            )
        ],
    )

    effect = execution_retry_request_effect(
        snapshot,
        "custom",
        ("WP-1",),
    )

    assert effect.snapshot is snapshot
    assert effect.selector == "custom"
    assert effect.package_ids == ("WP-1",)
    assert effect.show_retry_modal is True
    assert effect.no_packages_presentation is None


def test_run_execute_command_routes_instruction_to_controller() -> None:
    controller = _FakeExecuteController()

    run = run_execute_command(["retry", "interrupted"], controller)

    assert run.outcome is controller.outcome
    assert controller.instructions == ["retry interrupted"]


def test_execute_command_effect_prefers_execution_recovery() -> None:
    snapshot = WorkflowNexusSnapshot(session_id="wf-1")
    outcome = SimpleNamespace(
        snapshot=snapshot,
        execution_recovery_required=True,
        target_workspace_required=True,
    )

    effect = execute_command_effect(outcome, "Execution interrupted.")

    assert effect.presentation is None
    assert effect.execution_recovery_snapshot is snapshot
    assert effect.execution_recovery_message == "Execution interrupted."
    assert effect.workspace_picker_snapshot is None


def test_execute_command_effect_records_message_and_workspace_picker() -> None:
    snapshot = WorkflowNexusSnapshot(session_id="wf-1")
    outcome = SimpleNamespace(
        snapshot=snapshot,
        execution_recovery_required=False,
        target_workspace_required=True,
    )

    effect = execute_command_effect(
        outcome,
        "Finish planning before execution.",
        lang="ko",
    )

    assert effect.presentation is not None
    assert effect.presentation.title == "실행"
    assert effect.presentation.body == "Finish planning before execution."
    assert effect.workspace_picker_snapshot is snapshot
    assert effect.execution_recovery_snapshot is None


def test_execute_command_effect_skips_empty_message_without_workspace() -> None:
    outcome = SimpleNamespace(
        snapshot=WorkflowNexusSnapshot(session_id="wf-1"),
        execution_recovery_required=False,
        target_workspace_required=False,
    )

    effect = execute_command_effect(outcome, None)

    assert effect.presentation is None
    assert effect.execution_recovery_snapshot is None
    assert effect.workspace_picker_snapshot is None


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


class _FakeExecuteController:
    def __init__(self) -> None:
        self.outcome = object()
        self.instructions: list[str] = []

    def request_execution(self, instruction: str = "") -> object:
        self.instructions.append(instruction)
        return self.outcome
