"""Textual application shell for Trinity."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from trinity import __version__
from trinity.config import TrinityConfig
from trinity.textual_app.screens.nexus import NexusScreen
from trinity.textual_app.screens.settings import SettingsScreen
from trinity.textual_app.screens.start import StartScreen
from trinity.textual_app.settings import UISettingsStore
from trinity.textual_app.snapshot import NexusSnapshotAdapter
from trinity.textual_app.widgets.provider_inspector import ProviderInspector

WorkbenchRoute = Literal["start", "nexus", "execution", "settings"]


class PlaceholderScreen(Screen[None]):
    """Temporary route placeholder until the concrete screen is mounted."""

    def __init__(self, route: WorkbenchRoute, title: str, subtitle: str) -> None:
        super().__init__(name=route)
        self.route = route
        self.placeholder_title = title
        self.placeholder_subtitle = subtitle

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static(
            f"{self.placeholder_title}\n{self.placeholder_subtitle}",
            id="route-placeholder",
        )
        yield Footer()


class TrinityTextualApp(App[None]):
    """Desktop-style Textual workbench for Trinity."""

    TITLE = "Trinity"
    SUB_TITLE = f"v{__version__}"
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+n", "go_start", "New Session"),
        Binding("ctrl+1", "go_start", "Start"),
        Binding("ctrl+2", "go_nexus", "Nexus"),
        Binding("ctrl+3", "go_execution", "Execute"),
        Binding("ctrl+comma", "go_settings", "Settings"),
    ]

    CSS = """
    Screen {
        background: $surface;
    }

    #route-placeholder {
        width: 100%;
        height: 1fr;
        content-align: center middle;
        text-align: center;
        color: $text;
    }

    #start-screen {
        width: 100%;
        height: 1fr;
        align: center middle;
        padding: 1 2;
    }

    #start-title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        text-align: center;
        color: $accent;
    }

    #start-subtitle {
        width: 100%;
        content-align: center middle;
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }

    #start-composer {
        width: 72;
        max-width: 90%;
        height: 10;
        border: round $accent;
        padding: 0 1;
    }

    #prompt-textarea {
        height: 1fr;
        border: none;
    }

    #start-actions {
        width: 72;
        max-width: 90%;
        height: auto;
        margin-top: 1;
        align-horizontal: right;
    }

    #workspace-candidate {
        width: 1fr;
        color: $text-muted;
        content-align: left middle;
    }

    #nexus-screen {
        width: 100%;
        height: 1fr;
        padding: 1;
    }

    #provider-strip {
        width: 100%;
        height: 8;
        layout: grid;
        grid-size: 3 1;
        grid-gutter: 1;
    }

    .provider-panel {
        height: 8;
        border: round $accent;
        padding: 0 1;
    }

    .provider-claude {
        border: round $secondary;
    }

    .provider-codex {
        border: round $success;
    }

    .provider-antigravity {
        border: round $accent;
    }

    .provider-disabled {
        color: $text-muted;
    }

    .provider-name {
        text-style: bold;
    }

    .provider-meta {
        color: $text-muted;
    }

    .provider-status {
        margin-top: 1;
    }

    .provider-summary {
        color: $text-muted;
    }

    #central-agent {
        width: 1fr;
        height: 1fr;
        border: heavy white;
        padding: 1 2;
    }

    #nexus-main {
        height: 1fr;
        margin: 1 0;
    }

    #workflow-inspector {
        width: 32;
        min-width: 26;
        height: 1fr;
        border: round $primary;
        margin-left: 1;
        padding: 0 1;
    }

    .inspector-title {
        text-style: bold;
        color: $accent;
        margin-top: 1;
    }

    #central-title {
        text-style: bold;
        color: $text;
    }

    #central-body {
        height: 1fr;
        color: $text;
    }

    #central-markdown {
        height: 1fr;
    }

    #central-question-title {
        text-style: bold;
        color: $warning;
    }

    #central-questions {
        height: auto;
    }

    .question-text {
        margin-top: 1;
    }

    .question-options {
        height: auto;
        margin-bottom: 1;
    }

    #open-provider-inspector {
        width: 28;
        margin-top: 1;
    }

    ProviderInspector {
        align: center middle;
    }

    #provider-inspector {
        width: 88;
        max-width: 92%;
        height: 30;
        max-height: 92%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }

    #provider-inspector-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #provider-inspector-tabs {
        height: 1fr;
    }

    #settings-screen {
        width: 100%;
        height: 1fr;
        padding: 1 2;
    }

    #settings-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    .settings-row {
        width: 72;
        height: 3;
    }

    .settings-row Label {
        width: 22;
        content-align: left middle;
    }

    .settings-row Select {
        width: 32;
    }

    #theme-preview {
        width: 72;
        height: 7;
        border: round $accent;
        margin-top: 1;
        padding: 1 2;
    }

    #nexus-composer {
        width: 100%;
        height: 7;
        border: round $accent;
        padding: 0 1;
    }
    """

    def __init__(self, config: TrinityConfig) -> None:
        super().__init__()
        self.config = config
        self.current_route: WorkbenchRoute = "start"
        self.initial_prompt: str | None = None
        self.workspace_candidate: Path | None = None
        self.snapshot_adapter = NexusSnapshotAdapter(config)
        self.settings_store = UISettingsStore(config.effective_state_dir)
        self._screens_installed = False

    def on_mount(self) -> None:
        self._install_workbench_screens()
        self.current_route = "start"
        self.push_screen("start")

    def _install_workbench_screens(self) -> None:
        if self._screens_installed:
            return

        self.install_screen(StartScreen(self.workspace_candidate), "start")
        self.install_screen(NexusScreen(self.config), "nexus")
        self.install_screen(SettingsScreen(self.settings_store), "settings")

        screens: list[tuple[WorkbenchRoute, str, str]] = [
            ("execution", "Execution Matrix", "Work package execution monitor."),
        ]
        for route, title, subtitle in screens:
            self.install_screen(PlaceholderScreen(route, title, subtitle), route)
        self._screens_installed = True

    def on_start_screen_submitted(self, event: StartScreen.Submitted) -> None:
        event.stop()
        self.initial_prompt = event.prompt
        self.workspace_candidate = event.workspace_candidate
        nexus = self.get_screen("nexus", NexusScreen)
        nexus.set_initial_prompt(event.prompt)
        nexus.apply_snapshot(self.snapshot_adapter.load_snapshot())
        self.switch_to("nexus")

    def on_nexus_screen_follow_up_submitted(
        self,
        event: NexusScreen.FollowUpSubmitted,
    ) -> None:
        event.stop()

    def on_nexus_screen_question_answered(
        self,
        event: NexusScreen.QuestionAnswered,
    ) -> None:
        event.stop()

    def on_nexus_screen_inspector_requested(
        self,
        event: NexusScreen.InspectorRequested,
    ) -> None:
        event.stop()
        snapshot = event.snapshot or self.snapshot_adapter.load_snapshot()
        self.push_screen(ProviderInspector(snapshot.providers))

    def switch_to(self, route: WorkbenchRoute) -> None:
        if route == "nexus" and self._screens_installed:
            nexus = self.get_screen("nexus", NexusScreen)
            nexus.apply_snapshot(self.snapshot_adapter.load_snapshot())
        self.current_route = route
        self.switch_screen(route)

    def action_go_start(self) -> None:
        self.switch_to("start")

    def action_go_nexus(self) -> None:
        self.switch_to("nexus")

    def action_go_execution(self) -> None:
        self.switch_to("execution")

    def action_go_settings(self) -> None:
        self.switch_to("settings")


def run_textual_app(config: TrinityConfig) -> None:
    """Run the Textual workbench."""
    TrinityTextualApp(config).run()
