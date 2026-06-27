"""Pure helpers for Textual status command presentation."""

from __future__ import annotations

from trinity.textual_app import presenters as textual_presenters
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
