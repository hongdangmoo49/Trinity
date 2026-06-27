"""Pure helpers for Textual target command presentation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from trinity.textual_app import presenters as textual_presenters
from trinity.textual_app.command_parsers import parse_target_args
from trinity.textual_app.snapshot import LocalCommandSnapshot, WorkflowNexusSnapshot
from trinity.textual_app.target_workspace import (
    TargetWorkspacePreparation,
    is_control_repo_target,
    resolve_target_path,
)


TargetCommandActionKind = Literal["record", "clear", "confirm", "set"]
TargetCommandEffectKind = Literal["record", "clear", "confirm", "set", "none"]


@dataclass(frozen=True)
class TargetCommandPresentation:
    """Prepared local command result for `/target`."""

    title: str
    body: str
    severity: str = "info"
    empty: bool = False
    action_hint: str = ""
    table_columns: tuple[str, ...] = ()
    table_rows: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class TargetCommandAction:
    """Normalized app action for `/target`."""

    action: TargetCommandActionKind
    path: Path | None = None
    presentation: TargetCommandPresentation | None = None


@dataclass(frozen=True)
class TargetWorkspaceApplyEffect:
    """Prepared state changes after applying a target workspace."""

    resolved: Path
    snapshot: WorkflowNexusSnapshot
    presentation: TargetCommandPresentation
    workflow_outcome: Any | None = None

    @property
    def apply_workflow_outcome(self) -> bool:
        """Return whether the app should apply the controller workflow outcome."""
        return self.workflow_outcome is not None


@dataclass(frozen=True)
class TargetCommandEffect:
    """App effect derived from a normalized `/target` command action."""

    action: TargetCommandEffectKind
    path: Path | None = None
    presentation: TargetCommandPresentation | None = None


def target_current_presentation(
    current: str | None,
    *,
    lang: str = "en",
) -> TargetCommandPresentation:
    """Return presentation state for the current target workspace."""
    return TargetCommandPresentation(
        title=textual_presenters.target_title(lang=lang),
        body=textual_presenters.target_current_markdown(current, lang=lang),
        empty=current is None,
        action_hint=textual_presenters.target_action_hint(lang=lang),
    )


def target_cleared_presentation(*, lang: str = "en") -> TargetCommandPresentation:
    """Return presentation state after clearing the target workspace."""
    return TargetCommandPresentation(
        title=textual_presenters.target_title(lang=lang),
        body=textual_presenters.target_cleared_markdown(lang=lang),
    )


def target_not_directory_presentation(
    path: str,
    *,
    lang: str = "en",
) -> TargetCommandPresentation:
    """Return warning presentation when the target path is not a directory."""
    return TargetCommandPresentation(
        title=textual_presenters.target_title(lang=lang),
        body=textual_presenters.target_not_directory_markdown(path, lang=lang),
        severity="warning",
        empty=True,
    )


def target_prepare_failed_presentation(
    error: str,
    *,
    lang: str = "en",
) -> TargetCommandPresentation:
    """Return warning presentation when target workspace preparation fails."""
    return TargetCommandPresentation(
        title=textual_presenters.target_title(lang=lang),
        body=textual_presenters.target_prepare_failed_markdown(error, lang=lang),
        severity="warning",
        empty=True,
    )


def target_prepare_result_presentation(
    prepared: TargetWorkspacePreparation,
    *,
    lang: str = "en",
) -> TargetCommandPresentation | None:
    """Return a warning presentation for failed target workspace preparation."""
    if prepared.error == "not_directory":
        return target_not_directory_presentation(prepared.message, lang=lang)
    if prepared.error == "os_error":
        return target_prepare_failed_presentation(prepared.message, lang=lang)
    return None


def target_workspace_presentation(
    path: str,
    *,
    inside_control_repo: bool,
    control_repo_confirmed: bool,
    lang: str = "en",
) -> TargetCommandPresentation:
    """Return presentation state after setting the target workspace."""
    return TargetCommandPresentation(
        title=textual_presenters.target_title(lang=lang),
        body=textual_presenters.target_workspace_markdown(path, lang=lang),
        table_columns=textual_presenters.status_table_columns(lang=lang),
        table_rows=textual_presenters.target_rows(
            path,
            inside_control_repo=inside_control_repo,
            control_repo_confirmed=control_repo_confirmed,
            lang=lang,
        ),
    )


def target_set_presentation(
    path: Path,
    *,
    control_repo: Path,
    control_repo_confirmed: bool,
    lang: str = "en",
) -> TargetCommandPresentation:
    """Return presentation state after setting the target workspace path."""
    return target_workspace_presentation(
        str(path),
        inside_control_repo=is_control_repo_target(path, control_repo),
        control_repo_confirmed=control_repo_confirmed,
        lang=lang,
    )


def target_workspace_apply_effect(
    resolved: Path,
    outcome: Any,
    fallback_snapshot: WorkflowNexusSnapshot,
    *,
    control_repo: Path,
    control_repo_confirmed: bool,
    lang: str = "en",
) -> TargetWorkspaceApplyEffect:
    """Return app state changes after setting the target workspace."""
    outcome_snapshot = getattr(outcome, "snapshot", None)
    snapshot = outcome_snapshot if outcome_snapshot is not None else fallback_snapshot
    workflow_outcome = outcome if outcome_snapshot is not None else None
    return TargetWorkspaceApplyEffect(
        resolved=resolved,
        snapshot=snapshot,
        workflow_outcome=workflow_outcome,
        presentation=target_set_presentation(
            resolved,
            control_repo=control_repo,
            control_repo_confirmed=control_repo_confirmed,
            lang=lang,
        ),
    )


def target_command_action(
    args: list[str],
    *,
    current: Path | str | None,
    project_dir: Path,
    lang: str = "en",
) -> TargetCommandAction:
    """Parse `/target` arguments into the side effect the app should run."""
    parsed = parse_target_args(args)
    if parsed.action == "current":
        return TargetCommandAction(
            action="record",
            presentation=target_current_presentation(
                str(current) if current else None,
                lang=lang,
            ),
        )
    if parsed.action == "clear":
        return TargetCommandAction(action="clear")

    path = resolve_target_path(parsed.path_text, project_dir)
    if is_control_repo_target(path, project_dir):
        return TargetCommandAction(action="confirm", path=path)
    return TargetCommandAction(action="set", path=path)


def target_command_effect(action: TargetCommandAction) -> TargetCommandEffect:
    """Return the app effect for a normalized `/target` action."""
    if action.presentation is not None:
        return TargetCommandEffect(
            action="record",
            path=action.path,
            presentation=action.presentation,
        )
    if action.action == "clear":
        return TargetCommandEffect(action="clear")
    if action.path is None:
        return TargetCommandEffect(action="none")
    if action.action == "confirm":
        return TargetCommandEffect(action="confirm", path=action.path)
    return TargetCommandEffect(action="set", path=action.path)


def target_cancelled_snapshot(
    command: str = "/target",
    *,
    kind: str = "selection",
    lang: str = "en",
) -> LocalCommandSnapshot:
    """Return the local command snapshot for a cancelled target confirmation."""
    return textual_presenters.target_cancelled_local_command_snapshot(
        command,
        kind=kind,
        lang=lang,
    )
