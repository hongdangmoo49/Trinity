"""Pure local slash-command state helpers for Textual surfaces."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from trinity.textual_app.snapshot import LocalCommandSnapshot, WorkflowNexusSnapshot


def recent_local_command_results(
    results: Sequence[LocalCommandSnapshot],
    *,
    limit: int = 8,
) -> list[LocalCommandSnapshot]:
    """Return the bounded local command history shown in Textual snapshots."""
    if limit <= 0:
        return []
    return list(results[-limit:])


def snapshot_with_local_command_results(
    snapshot: WorkflowNexusSnapshot,
    results: Sequence[LocalCommandSnapshot],
    *,
    limit: int = 8,
) -> WorkflowNexusSnapshot:
    """Attach bounded local command results to a workflow snapshot."""
    return replace(
        snapshot,
        local_commands=recent_local_command_results(results, limit=limit),
    )


def replace_local_command_result(
    results: Sequence[LocalCommandSnapshot],
    result: LocalCommandSnapshot,
) -> list[LocalCommandSnapshot]:
    """Keep only the latest result for a local slash command."""
    return [item for item in results if item.command != result.command] + [result]
