"""Pure helpers for Textual status command presentation."""

from __future__ import annotations

from trinity.textual_app import presenters as textual_presenters
from trinity.textual_app.local_commands import (
    LocalCommandResultEffect,
    local_command_result_effect,
)
from trinity.textual_app.snapshot import LocalCommandSnapshot, WorkflowNexusSnapshot


def status_command_result(
    command: str,
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> LocalCommandSnapshot:
    """Return the prepared local command result for `/status`."""
    return textual_presenters.status_local_command_snapshot(
        command,
        snapshot,
        lang=lang,
    )


def status_command_effect(
    command: str,
    snapshot: WorkflowNexusSnapshot,
    local_command_results: list[LocalCommandSnapshot],
    *,
    current_route: str,
    lang: str = "en",
) -> LocalCommandResultEffect:
    """Return UI state changes for rendering `/status`."""
    result = status_command_result(command, snapshot, lang=lang)
    return local_command_result_effect(
        result,
        snapshot,
        local_command_results,
        current_route=current_route,
        notify=False,
        lang=lang,
    )
