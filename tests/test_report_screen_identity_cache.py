from __future__ import annotations

import pytest
from textual.app import App

from trinity.textual_app.screens.report import ReportScreen
from trinity.textual_app.snapshot import WorkflowNexusSnapshot
from trinity.tui.report import DeliberationReport, ReportMeta


class ReportHarness(App[None]):
    def __init__(self, screen: ReportScreen) -> None:
        super().__init__()
        self.report = screen

    def on_mount(self) -> None:
        self.push_screen(self.report)


def _snapshot(*, goal: str = "Inspect project") -> WorkflowNexusSnapshot:
    return WorkflowNexusSnapshot(
        session_id="wf-report-cache",
        goal=goal,
        state="reviewing",
    )


def _report(*, goal: str = "Inspect project") -> DeliberationReport:
    return DeliberationReport(
        meta=ReportMeta(
            session_id="wf-report-cache",
            goal=goal,
            created_at="2026-06-25 00:00:00",
            agents=("claude", "codex"),
            rounds=1,
            duration="N/A",
            tokens="N/A",
            state="reviewing",
        ),
        consensus=None,
        blueprint=None,
        decisions=(),
        packages=(),
        executions=(),
    )


@pytest.mark.asyncio
async def test_report_screen_skips_same_snapshot_object_reapply() -> None:
    screen = ReportScreen()
    snapshot = _snapshot()
    app = ReportHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        screen.apply_snapshot(snapshot)
        await pilot.pause()

        calls: list[str] = []

        def counted_render() -> None:
            calls.append("render")

        screen._render_report = counted_render

        screen.apply_snapshot(snapshot)
        await pilot.pause()
        assert calls == []

        screen.apply_snapshot(_snapshot())
        await pilot.pause()
        assert calls == ["render"]


@pytest.mark.asyncio
async def test_report_screen_skips_same_structured_report_object_reapply() -> None:
    screen = ReportScreen()
    report = _report()
    app = ReportHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        screen.apply_report(report)
        await pilot.pause()

        calls: list[str] = []

        def counted_render() -> None:
            calls.append("render")

        screen._render_report = counted_render

        screen.apply_report(report)
        await pilot.pause()
        assert calls == []

        screen.apply_report(_report())
        await pilot.pause()
        assert calls == ["render"]
