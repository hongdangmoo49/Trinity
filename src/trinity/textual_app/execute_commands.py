"""Pure helpers for Textual execute command presentation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from trinity.textual_app import presenters as textual_presenters
from trinity.textual_app.command_parsers import parse_execute_args
from trinity.textual_app.snapshot import LocalCommandSnapshot, WorkflowNexusSnapshot


ExecuteSeverity = Literal["warning"]


@dataclass(frozen=True)
class ExecuteCommandPresentation:
    """Prepared local command result or notification for execute actions."""

    title: str
    body: str
    severity: ExecuteSeverity = "warning"
    empty: bool = True
    action_hint: str = ""


class ExecuteWorkflowController(Protocol):
    """Workflow controller surface required by `/execute`."""

    def request_execution(self, instruction: str = "") -> Any:
        """Request execution for the current workflow."""


@dataclass(frozen=True)
class ExecuteCommandRun:
    """Workflow outcome produced by `/execute`."""

    outcome: Any


@dataclass(frozen=True)
class ExecuteCommandEffect:
    """UI effects derived from an execute workflow outcome."""

    presentation: ExecuteCommandPresentation | None = None
    execution_recovery_snapshot: WorkflowNexusSnapshot | None = None
    execution_recovery_message: str = ""
    workspace_picker_snapshot: WorkflowNexusSnapshot | None = None


@dataclass(frozen=True)
class ExecutionRetryRequestEffect:
    """UI effects derived from an execution retry request."""

    snapshot: WorkflowNexusSnapshot
    selector: str
    package_ids: tuple[str, ...] = ()
    no_packages_presentation: ExecuteCommandPresentation | None = None

    @property
    def show_retry_modal(self) -> bool:
        """Return whether the retry confirmation modal should be shown."""
        return self.no_packages_presentation is None


def run_execute_command(
    args: list[str],
    controller: ExecuteWorkflowController,
) -> ExecuteCommandRun:
    """Parse `/execute` arguments and request workflow execution."""
    parsed_execute = parse_execute_args(args)
    return ExecuteCommandRun(
        outcome=controller.request_execution(parsed_execute.instruction)
    )


def execute_command_effect(
    outcome: Any,
    message: str | None,
    *,
    lang: str = "en",
) -> ExecuteCommandEffect:
    """Return the UI effects the app should apply after `/execute`."""
    if getattr(outcome, "execution_recovery_required", False):
        return ExecuteCommandEffect(
            execution_recovery_snapshot=outcome.snapshot,
            execution_recovery_message=message or "",
        )
    presentation = execute_result_presentation(message, lang=lang)
    workspace_picker_snapshot = None
    if getattr(outcome, "target_workspace_required", False):
        workspace_picker_snapshot = outcome.snapshot
    return ExecuteCommandEffect(
        presentation=presentation,
        workspace_picker_snapshot=workspace_picker_snapshot,
    )


def execute_result_presentation(
    message: str | None,
    *,
    lang: str = "en",
) -> ExecuteCommandPresentation | None:
    """Return presentation state for an execute workflow outcome message."""
    if not message:
        return None
    return ExecuteCommandPresentation(
        title=textual_presenters.execute_title(lang=lang),
        body=textual_presenters.workflow_outcome_message_markdown(message, lang=lang),
        action_hint=textual_presenters.execute_finish_planning_action_hint(lang=lang),
    )


def execute_retry_no_packages_presentation(
    *,
    lang: str = "en",
) -> ExecuteCommandPresentation:
    """Return presentation state when execute retry has no work packages."""
    return ExecuteCommandPresentation(
        title=textual_presenters.execute_retry_title(lang=lang),
        body=textual_presenters.execute_retry_no_packages_markdown(lang=lang),
        action_hint=textual_presenters.execute_retry_no_packages_action_hint(
            lang=lang
        ),
    )


def execution_retry_request_effect(
    snapshot: WorkflowNexusSnapshot,
    selector: str,
    package_ids: tuple[str, ...],
    *,
    lang: str = "en",
) -> ExecutionRetryRequestEffect:
    """Return UI effects for an Execution Matrix retry request."""
    presentation = None
    if not snapshot.work_package_details:
        presentation = execute_retry_no_packages_presentation(lang=lang)
    return ExecutionRetryRequestEffect(
        snapshot=snapshot,
        selector=selector,
        package_ids=package_ids,
        no_packages_presentation=presentation,
    )


def execution_recovery_snapshot(
    command: str,
    snapshot: WorkflowNexusSnapshot,
    message: str = "",
    *,
    lang: str = "en",
) -> LocalCommandSnapshot:
    """Return the local command snapshot for interrupted execution recovery."""
    return textual_presenters.execution_recovery_local_command_snapshot(
        command,
        snapshot,
        message,
        lang=lang,
    )
