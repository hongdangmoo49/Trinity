"""Helpers for applying workflow snapshots to the active Textual route."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, Protocol, TypeVar

from trinity.textual_app.screens.execution_matrix import ExecutionMatrixScreen
from trinity.textual_app.screens.nexus import NexusScreen
from trinity.textual_app.screens.report import ReportScreen
from trinity.textual_app.snapshot import WorkflowNexusSnapshot
from trinity.textual_app.widgets.workspace_picker import WorkspacePreflight

WorkbenchRoute = Literal["start", "nexus", "execution", "settings", "report"]

_ScreenT = TypeVar("_ScreenT")


class RouteSnapshotHost(Protocol):
    """Small host surface needed to resolve Textual screens."""

    def get_screen(self, name: str, screen_type: type[_ScreenT]) -> _ScreenT:
        """Return the mounted Textual screen for the given route."""


def apply_current_route_snapshot(
    host: RouteSnapshotHost,
    route: WorkbenchRoute,
    snapshot: WorkflowNexusSnapshot,
    *,
    confirmed_preflight: WorkspacePreflight | None,
    sync_nexus_workspace_candidate: Callable[[], None],
) -> bool:
    """Apply a workflow snapshot to the screen backing the current route."""
    if route == "nexus":
        sync_nexus_workspace_candidate()
        host.get_screen("nexus", NexusScreen).apply_snapshot(snapshot)
        return True
    if route == "execution" and confirmed_preflight is not None:
        host.get_screen("execution", ExecutionMatrixScreen).apply_execution_state(
            confirmed_preflight,
            snapshot,
        )
        return True
    if route == "report":
        host.get_screen("report", ReportScreen).apply_snapshot(snapshot)
        return True
    return False
