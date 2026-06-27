"""Pure helpers for Textual context command presentation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from trinity.textual_app import presenters as textual_presenters
from trinity.textual_app.local_commands import (
    replace_local_command_result,
    snapshot_with_local_command_results,
)
from trinity.textual_app.snapshot import LocalCommandSnapshot, WorkflowNexusSnapshot


ContextCommandAction = Literal["notify", "record", "modal", "apply_snapshot"]
ContextCommandEffectAction = Literal[
    "notify",
    "record",
    "modal",
    "workflow_outcome",
    "none",
]
ContextSeverity = Literal["info", "warning"]


@dataclass(frozen=True)
class ContextCommandPresentation:
    """Prepared route action for `/context`."""

    action: ContextCommandAction
    command: str
    title: str
    body: str
    severity: ContextSeverity = "info"
    result: LocalCommandSnapshot | None = None


@dataclass(frozen=True)
class ContextCommandSnapshotUpdate:
    """Updated local command state and snapshot for `/context` result rendering."""

    local_command_results: list[LocalCommandSnapshot]
    snapshot: WorkflowNexusSnapshot
    result: LocalCommandSnapshot


@dataclass(frozen=True)
class ContextCommandEffect:
    """Concrete UI effect derived from a `/context` presentation."""

    action: ContextCommandEffectAction
    command: str = ""
    title: str = ""
    body: str = ""
    severity: ContextSeverity = "info"
    local_command_results: list[LocalCommandSnapshot] | None = None
    snapshot: WorkflowNexusSnapshot | None = None
    result: LocalCommandSnapshot | None = None


def context_command_presentation(
    command: str,
    snapshot: WorkflowNexusSnapshot,
    *,
    route: str,
    lang: str = "en",
) -> ContextCommandPresentation:
    """Return the presentation action for a Textual `/context` command."""
    title = textual_presenters.context_title(lang=lang)
    body = textual_presenters.snapshot_context_markdown(snapshot, lang=lang)
    if not textual_presenters.snapshot_has_current_context(snapshot):
        if route == "start":
            return ContextCommandPresentation(
                action="notify",
                command=command,
                title=title,
                body=textual_presenters.context_no_current_markdown(lang=lang),
                severity="warning",
            )
        return ContextCommandPresentation(
            action="record",
            command=command,
            title=title,
            body=body,
        )

    result = textual_presenters.local_command_snapshot(command, title, body)
    return ContextCommandPresentation(
        action="modal" if route == "start" else "apply_snapshot",
        command=command,
        title=title,
        body=body,
        result=result,
    )


def context_command_snapshot_update(
    presentation: ContextCommandPresentation,
    snapshot: WorkflowNexusSnapshot,
    local_command_results: Sequence[LocalCommandSnapshot],
) -> ContextCommandSnapshotUpdate | None:
    """Return updated local command state for a context command result."""
    result = presentation.result
    if result is None:
        return None
    updated_results = replace_local_command_result(local_command_results, result)
    updated_snapshot = snapshot_with_local_command_results(snapshot, updated_results)
    return ContextCommandSnapshotUpdate(
        local_command_results=updated_results,
        snapshot=updated_snapshot,
        result=result,
    )


def context_command_effect(
    presentation: ContextCommandPresentation,
    snapshot: WorkflowNexusSnapshot,
    local_command_results: Sequence[LocalCommandSnapshot],
) -> ContextCommandEffect:
    """Return the concrete Textual effect for a context command presentation."""
    if presentation.action in {"notify", "record"}:
        return ContextCommandEffect(
            action=presentation.action,
            command=presentation.command,
            title=presentation.title,
            body=presentation.body,
            severity=presentation.severity,
        )

    update = context_command_snapshot_update(
        presentation,
        snapshot,
        local_command_results,
    )
    if update is None:
        return ContextCommandEffect(action="none")
    return ContextCommandEffect(
        action="modal" if presentation.action == "modal" else "workflow_outcome",
        local_command_results=update.local_command_results,
        snapshot=update.snapshot,
        result=update.result,
    )
