"""Helpers for preparing the Textual report route."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from trinity.textual_app.snapshot import WorkflowNexusSnapshot
from trinity.tui.report import DeliberationReport, DeliberationReportBuilder
from trinity.workflow import WorkflowPersistence


class ReportRouteScreen(Protocol):
    """Small screen surface needed to prepare the report route."""

    def apply_snapshot(self, snapshot: WorkflowNexusSnapshot) -> None:
        """Apply the fallback workflow snapshot."""

    def apply_report(self, report: DeliberationReport) -> None:
        """Apply the structured deliberation report."""


def prepare_report_route(
    screen: ReportRouteScreen,
    snapshot: WorkflowNexusSnapshot,
    *,
    state_dir: Path,
    event_limit: int,
    structured_snapshot: WorkflowNexusSnapshot | None = None,
) -> bool:
    """Apply report route data and return whether structured rendering was used."""
    screen.apply_snapshot(snapshot)
    try:
        persistence = WorkflowPersistence(state_dir)
        session = persistence.load()
        if not session or not session.goal:
            return False
        events = persistence.load_events_for_workflow(
            session.id,
            tail=event_limit,
        )
        structured = DeliberationReportBuilder(
            session,
            result=None,
            events=events,
            snapshot=structured_snapshot,
        ).build()
        screen.apply_report(structured)
        return True
    except Exception:
        return False
