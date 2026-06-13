"""Replay helpers for persisted Trinity workflow sessions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from trinity.config import TrinityConfig
from trinity.textual_app.snapshot import NexusSnapshotAdapter, WorkflowNexusSnapshot
from trinity.tui.report import DeliberationReport, DeliberationReportBuilder
from trinity.workflow import WorkflowPersistence, WorkflowSession


@dataclass(frozen=True)
class WorkflowReplay:
    """Reconstructed workflow projections from persisted state."""

    config: TrinityConfig
    persistence: WorkflowPersistence
    session: WorkflowSession
    events: tuple[dict[str, object], ...]
    snapshot: WorkflowNexusSnapshot
    report: DeliberationReport


def replay_workflow(project_dir: Path) -> WorkflowReplay:
    """Load persisted workflow state and reconstruct snapshot/report outputs."""
    config = TrinityConfig.default_config(project_dir=project_dir)
    persistence = WorkflowPersistence(config.effective_state_dir)
    session = persistence.load()
    if session is None:
        raise FileNotFoundError(f"No workflow session found under {config.effective_state_dir}")
    events = tuple(persistence.load_events_for_workflow(session.id))
    snapshot = NexusSnapshotAdapter(config).load_snapshot()
    report = DeliberationReportBuilder(session, events=events).build()
    return WorkflowReplay(
        config=config,
        persistence=persistence,
        session=session,
        events=events,
        snapshot=snapshot,
        report=report,
    )
