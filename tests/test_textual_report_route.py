from __future__ import annotations

from trinity.textual_app.report_route import prepare_report_route
from trinity.textual_app.snapshot import WorkflowNexusSnapshot
from trinity.tui.report import DeliberationReport
from trinity.workflow import WorkflowPersistence, WorkflowSession, WorkflowState


class FakeReportScreen:
    def __init__(self, *, fail_report: bool = False) -> None:
        self.fail_report = fail_report
        self.events: list[tuple[str, object]] = []

    def apply_snapshot(self, snapshot: WorkflowNexusSnapshot) -> None:
        self.events.append(("snapshot", snapshot.session_id))

    def apply_report(self, report: DeliberationReport) -> None:
        if self.fail_report:
            raise RuntimeError("report render failed")
        self.events.append(("report", report.meta.session_id))


def test_prepare_report_route_applies_snapshot_without_session(tmp_path) -> None:
    screen = FakeReportScreen()
    snapshot = WorkflowNexusSnapshot(session_id="wf-snapshot")

    structured = prepare_report_route(
        screen,
        snapshot,
        state_dir=tmp_path,
        event_limit=20,
        structured_snapshot=snapshot,
    )

    assert structured is False
    assert screen.events == [("snapshot", "wf-snapshot")]


def test_prepare_report_route_applies_structured_report_when_session_exists(
    tmp_path,
) -> None:
    WorkflowPersistence(tmp_path).save(
        WorkflowSession(
            id="wf-report",
            goal="render report",
            state=WorkflowState.BLUEPRINT_READY,
        )
    )
    screen = FakeReportScreen()
    snapshot = WorkflowNexusSnapshot(session_id="wf-snapshot")

    structured = prepare_report_route(
        screen,
        snapshot,
        state_dir=tmp_path,
        event_limit=20,
        structured_snapshot=snapshot,
    )

    assert structured is True
    assert screen.events == [
        ("snapshot", "wf-snapshot"),
        ("report", "wf-report"),
    ]


def test_prepare_report_route_keeps_snapshot_fallback_when_structured_apply_fails(
    tmp_path,
) -> None:
    WorkflowPersistence(tmp_path).save(
        WorkflowSession(
            id="wf-report",
            goal="render report",
            state=WorkflowState.BLUEPRINT_READY,
        )
    )
    screen = FakeReportScreen(fail_report=True)
    snapshot = WorkflowNexusSnapshot(session_id="wf-snapshot")

    structured = prepare_report_route(
        screen,
        snapshot,
        state_dir=tmp_path,
        event_limit=20,
        structured_snapshot=snapshot,
    )

    assert structured is False
    assert screen.events == [("snapshot", "wf-snapshot")]
