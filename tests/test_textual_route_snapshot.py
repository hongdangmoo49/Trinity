from __future__ import annotations

from types import SimpleNamespace

from trinity.textual_app.route_snapshot import apply_current_route_snapshot
from trinity.textual_app.snapshot import WorkflowNexusSnapshot


class FakeNexusScreen:
    def __init__(self, events: list[object]) -> None:
        self.events = events

    def apply_snapshot(self, snapshot: WorkflowNexusSnapshot) -> None:
        self.events.append(("nexus", snapshot.session_id))


class FakeExecutionScreen:
    def __init__(self, events: list[object]) -> None:
        self.events = events

    def apply_execution_state(
        self,
        preflight: object,
        snapshot: WorkflowNexusSnapshot,
    ) -> None:
        self.events.append(("execution", preflight, snapshot.session_id))


class FakeReportScreen:
    def __init__(self, events: list[object]) -> None:
        self.events = events

    def apply_snapshot(self, snapshot: WorkflowNexusSnapshot) -> None:
        self.events.append(("report", snapshot.session_id))


class FakeRouteHost:
    def __init__(self) -> None:
        self.events: list[object] = []
        self.screens = {
            "nexus": FakeNexusScreen(self.events),
            "execution": FakeExecutionScreen(self.events),
            "report": FakeReportScreen(self.events),
        }

    def get_screen(self, name: str, screen_type: type[object]) -> object:
        self.events.append(("get_screen", name, screen_type.__name__))
        return self.screens[name]


def test_apply_current_route_snapshot_syncs_and_updates_nexus() -> None:
    host = FakeRouteHost()
    snapshot = WorkflowNexusSnapshot(session_id="wf-route")

    applied = apply_current_route_snapshot(
        host,
        "nexus",
        snapshot,
        confirmed_preflight=None,
        sync_nexus_workspace_candidate=lambda: host.events.append("sync"),
    )

    assert applied is True
    assert host.events == [
        "sync",
        ("get_screen", "nexus", "NexusScreen"),
        ("nexus", "wf-route"),
    ]


def test_apply_current_route_snapshot_updates_execution_with_preflight() -> None:
    host = FakeRouteHost()
    snapshot = WorkflowNexusSnapshot(session_id="wf-route")
    preflight = SimpleNamespace(target_workspace="/tmp/project")

    applied = apply_current_route_snapshot(
        host,
        "execution",
        snapshot,
        confirmed_preflight=preflight,
        sync_nexus_workspace_candidate=lambda: host.events.append("sync"),
    )

    assert applied is True
    assert host.events == [
        ("get_screen", "execution", "ExecutionMatrixScreen"),
        ("execution", preflight, "wf-route"),
    ]


def test_apply_current_route_snapshot_skips_execution_without_preflight() -> None:
    host = FakeRouteHost()
    snapshot = WorkflowNexusSnapshot(session_id="wf-route")

    applied = apply_current_route_snapshot(
        host,
        "execution",
        snapshot,
        confirmed_preflight=None,
        sync_nexus_workspace_candidate=lambda: host.events.append("sync"),
    )

    assert applied is False
    assert host.events == []


def test_apply_current_route_snapshot_updates_report() -> None:
    host = FakeRouteHost()
    snapshot = WorkflowNexusSnapshot(session_id="wf-route")

    applied = apply_current_route_snapshot(
        host,
        "report",
        snapshot,
        confirmed_preflight=None,
        sync_nexus_workspace_candidate=lambda: host.events.append("sync"),
    )

    assert applied is True
    assert host.events == [
        ("get_screen", "report", "ReportScreen"),
        ("report", "wf-route"),
    ]


def test_apply_current_route_snapshot_ignores_routes_without_snapshot_surface() -> None:
    host = FakeRouteHost()
    snapshot = WorkflowNexusSnapshot(session_id="wf-route")

    applied = apply_current_route_snapshot(
        host,
        "settings",
        snapshot,
        confirmed_preflight=None,
        sync_nexus_workspace_candidate=lambda: host.events.append("sync"),
    )

    assert applied is False
    assert host.events == []
