"""Workbench screen construction helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from textual.screen import Screen

from trinity.config import TrinityConfig
from trinity.textual_app.route_snapshot import WorkbenchRoute
from trinity.textual_app.screens.execution_matrix import ExecutionMatrixScreen
from trinity.textual_app.screens.nexus import NexusScreen
from trinity.textual_app.screens.report import ReportScreen
from trinity.textual_app.screens.settings import SettingsScreen
from trinity.textual_app.screens.start import StartScreen
from trinity.textual_app.settings import UISettingsStore


@dataclass(frozen=True)
class WorkbenchScreenSpec:
    """Screen instance and route name to install in the Textual workbench."""

    route: WorkbenchRoute
    screen: Screen[None]


def workbench_screen_specs(
    config: TrinityConfig,
    settings_store: UISettingsStore,
    workspace_candidate: Path | None,
) -> tuple[WorkbenchScreenSpec, ...]:
    """Build the default Textual workbench screens in install order."""
    return (
        WorkbenchScreenSpec(
            "start",
            StartScreen(config, workspace_candidate, lang=config.lang),
        ),
        WorkbenchScreenSpec("nexus", NexusScreen(config)),
        WorkbenchScreenSpec(
            "settings",
            SettingsScreen(settings_store, config, lang=config.lang),
        ),
        WorkbenchScreenSpec(
            "execution",
            ExecutionMatrixScreen(lang=config.lang),
        ),
        WorkbenchScreenSpec("report", ReportScreen(lang=config.lang)),
    )
