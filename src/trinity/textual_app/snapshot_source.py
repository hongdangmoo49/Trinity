"""Snapshot selection helpers for the Textual app shell."""

from __future__ import annotations

from collections.abc import Callable

from trinity.textual_app.snapshot import WorkflowNexusSnapshot

SnapshotLoader = Callable[[], WorkflowNexusSnapshot | None]


def current_textual_snapshot(
    *,
    active_snapshot: WorkflowNexusSnapshot | None,
    controller_snapshot: SnapshotLoader,
    persisted_snapshot: Callable[[], WorkflowNexusSnapshot],
) -> WorkflowNexusSnapshot:
    """Return active, controller, then persisted snapshot in priority order."""
    if active_snapshot is not None:
        return active_snapshot
    snapshot = controller_snapshot()
    if snapshot is not None:
        return snapshot
    return persisted_snapshot()


def fresh_textual_snapshot(
    *,
    controller_snapshot: SnapshotLoader,
    persisted_snapshot: Callable[[], WorkflowNexusSnapshot],
) -> WorkflowNexusSnapshot:
    """Return the latest controller or persisted snapshot, ignoring active UI state."""
    return controller_snapshot() or persisted_snapshot()
