"""Textual application shell for Trinity."""

from __future__ import annotations

from typing import Literal

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from trinity import __version__
from trinity.config import TrinityConfig

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
    """

    def __init__(self, config: TrinityConfig) -> None:
        super().__init__()
        self.config = config
        self.current_route: WorkbenchRoute = "start"
        self._screens_installed = False

    def on_mount(self) -> None:
        self._install_workbench_screens()
        self.current_route = "start"
        self.push_screen("start")

    def _install_workbench_screens(self) -> None:
        if self._screens_installed:
            return

        screens: list[tuple[WorkbenchRoute, str, str]] = [
            ("start", "TRINITY", "Start screen will collect the first prompt."),
            ("nexus", "Nexus", "Provider brainstorming dashboard."),
            ("execution", "Execution Matrix", "Work package execution monitor."),
            ("settings", "Settings", "Theme preferences."),
        ]
        for route, title, subtitle in screens:
            self.install_screen(PlaceholderScreen(route, title, subtitle), route)
        self._screens_installed = True

    def switch_to(self, route: WorkbenchRoute) -> None:
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
