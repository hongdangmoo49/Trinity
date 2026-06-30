"""Pure helpers for Textual status command presentation."""

from __future__ import annotations

from dataclasses import replace

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
    extra_table_rows: tuple[tuple[str, str], ...] = (),
    lang: str = "en",
) -> LocalCommandSnapshot:
    """Return the prepared local command result for `/status`."""
    result = textual_presenters.status_local_command_snapshot(
        command,
        snapshot,
        lang=lang,
    )
    if not extra_table_rows:
        return result
    return replace(result, table_rows=result.table_rows + extra_table_rows)


def status_command_effect(
    command: str,
    snapshot: WorkflowNexusSnapshot,
    local_command_results: list[LocalCommandSnapshot],
    *,
    current_route: str,
    extra_table_rows: tuple[tuple[str, str], ...] = (),
    lang: str = "en",
) -> LocalCommandResultEffect:
    """Return UI state changes for rendering `/status`."""
    result = status_command_result(
        command,
        snapshot,
        extra_table_rows=extra_table_rows,
        lang=lang,
    )
    return local_command_result_effect(
        result,
        snapshot,
        local_command_results,
        current_route=current_route,
        notify=False,
        lang=lang,
    )
