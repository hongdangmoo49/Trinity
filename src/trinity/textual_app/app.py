"""Textual application shell for Trinity."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from textual.app import App
from textual.binding import Binding

from trinity import __version__
from trinity.config import TrinityConfig
from trinity.textual_app.report_export import (
    snapshot_has_report_data,
    snapshot_report_markdown,
    unique_report_path,
)
from trinity.textual_app.screens.execution_matrix import ExecutionMatrixScreen
from trinity.textual_app.screens.nexus import NexusScreen
from trinity.textual_app.screens.report import ReportScreen
from trinity.textual_app.screens.settings import SettingsScreen
from trinity.textual_app.screens.start import StartScreen
from trinity.textual_app.settings import UISettingsStore
from trinity.textual_app.snapshot import NexusSnapshotAdapter, WorkflowNexusSnapshot
from trinity.textual_app.widgets.provider_inspector import ProviderInspector
from trinity.textual_app.widgets.workspace_picker import WorkspacePicker, WorkspacePreflight
from trinity.tui.kitty_compat import install_textual_parser_patch

WorkbenchRoute = Literal["start", "nexus", "execution", "settings", "report"]


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
        Binding("ctrl+4", "go_report", "Report"),
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

    #start-shell {
        width: 72;
        max-width: 90%;
        height: auto;
    }

    #start-geometry {
        width: 100%;
        height: 14;
        content-align: center middle;
        text-align: center;
        color: $accent;
        margin-bottom: 1;
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
        width: 100%;
        height: 10;
        border: round $accent;
        padding: 0 1;
    }

    #start-composer.-commands-open {
        height: 13;
    }

    #prompt-textarea {
        height: 1fr;
        border: none;
    }

    #start-actions {
        width: 100%;
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
        overflow-y: auto;
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
        height: auto;
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
        layout: grid;
        grid-size: 2;
        grid-gutter: 1;
        height: auto;
        margin-bottom: 1;
    }

    .question-options Button {
        width: 100%;
    }

    #provider-inspector TabPane {
        height: 1fr;
    }

    .provider-inspector-meta {
        height: auto;
        color: $text-muted;
        margin-bottom: 1;
    }

    .provider-inspector-output {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
    }

    #nexus-action-bar {
        height: auto;
        margin-top: 1;
    }

    #open-provider-inspector {
        width: 28;
    }

    #request-execute {
        width: 16;
        margin-left: 1;
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

    WorkspacePicker {
        align: center middle;
    }

    #workspace-picker {
        width: 96;
        max-width: 94%;
        height: 34;
        max-height: 94%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }

    #workspace-picker-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #workspace-picker-body {
        height: 1fr;
        margin-top: 1;
    }

    #workspace-directory-tree {
        width: 1fr;
        height: 1fr;
        border: round $primary;
    }

    #workspace-preflight {
        width: 38;
        height: 1fr;
        margin-left: 1;
        border: round $secondary;
        padding: 1;
    }

    #workspace-picker-actions {
        height: auto;
        margin-top: 1;
        align-horizontal: right;
    }

    #execution-screen {
        width: 100%;
        height: 1fr;
        padding: 1;
    }

    #execution-header {
        height: 1;
        text-style: bold;
        color: $accent;
    }

    #execution-table {
        height: 11;
        margin-top: 1;
    }

    #execution-log {
        height: 1fr;
        border: round $primary;
        margin-top: 1;
        padding: 0 1;
    }

    #report-screen {
        width: 100%;
        height: 1fr;
        padding: 1 2;
    }

    #report-header {
        height: 4;
        margin-bottom: 1;
    }

    #report-title {
        text-style: bold;
        color: $accent;
    }

    #report-export-btn {
        margin-top: 1;
    }

    #report-export-status {
        color: $text-muted;
    }

    #report-body {
        height: 1fr;
        border: round $primary;
        padding: 1 2;
    }

    #nexus-composer {
        width: 100%;
        height: 7;
        border: round $accent;
        padding: 0 1;
    }

    #nexus-composer.-commands-open {
        height: 13;
    }

    #prompt-command-palette {
        display: none;
        width: 100%;
        max-height: 9;
        height: auto;
        border: round $primary;
        margin-top: 1;
        padding: 0 1;
        background: $surface;
    }

    .command-option {
        height: 1;
        color: $text-muted;
    }

    .command-option-selected {
        color: $accent;
        text-style: bold reverse;
    }

    .command-option-first {
        color: $accent;
        text-style: bold;
    }

    .command-option-empty {
        color: $warning;
    }

    .command-option-more {
        color: $text-muted;
        text-style: italic;
    }
    """

    def __init__(self, config: TrinityConfig) -> None:
        install_textual_parser_patch()
        super().__init__()
        self.config = config
        self.current_route: WorkbenchRoute = "start"
        self.initial_prompt: str | None = None
        self.workspace_candidate: Path | None = None
        self.snapshot_adapter = NexusSnapshotAdapter(config)
        self.active_snapshot: WorkflowNexusSnapshot | None = None
        self.settings_store = UISettingsStore(config.effective_state_dir)
        self.confirmed_preflight: WorkspacePreflight | None = None
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
        self.install_screen(ExecutionMatrixScreen(), "execution")
        self.install_screen(ReportScreen(), "report")

        self._screens_installed = True

    def on_start_screen_submitted(self, event: StartScreen.Submitted) -> None:
        event.stop()
        self.initial_prompt = event.prompt
        self.workspace_candidate = event.workspace_candidate
        snapshot = self.snapshot_adapter.new_session_snapshot(event.prompt)
        self.active_snapshot = snapshot
        nexus = self.get_screen("nexus", NexusScreen)
        nexus.set_initial_prompt(event.prompt)
        nexus.apply_snapshot(snapshot)
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
        snapshot = (
            event.snapshot
            or self.active_snapshot
            or self.snapshot_adapter.load_snapshot()
        )
        self.push_screen(ProviderInspector(snapshot.providers))

    def on_nexus_screen_execute_requested(
        self,
        event: NexusScreen.ExecuteRequested,
    ) -> None:
        event.stop()
        snapshot = (
            event.snapshot
            or self.active_snapshot
            or self.snapshot_adapter.load_snapshot()
        )
        self.push_screen(
            WorkspacePicker(
                candidate=self.workspace_candidate,
                snapshot=snapshot,
                cwd=self.config.project_dir,
            ),
            self._on_workspace_preflight,
        )

    def _on_workspace_preflight(self, preflight: WorkspacePreflight | None) -> None:
        if preflight is None:
            return
        self.confirmed_preflight = preflight
        snapshot = self.active_snapshot or self.snapshot_adapter.load_snapshot()
        execution = self.get_screen("execution", ExecutionMatrixScreen)
        execution.apply_execution_state(preflight, snapshot)
        self.switch_to("execution")

    def switch_to(self, route: WorkbenchRoute) -> None:
        if route == "nexus" and self._screens_installed:
            nexus = self.get_screen("nexus", NexusScreen)
            nexus.apply_snapshot(
                self.active_snapshot or self.snapshot_adapter.load_snapshot()
            )
        if route == "report" and self._screens_installed:
            report = self.get_screen("report", ReportScreen)
            report.apply_snapshot(
                self.active_snapshot or self.snapshot_adapter.load_snapshot()
            )
            # Build a structured DeliberationReport for richer rendering
            try:
                from trinity.tui.report import DeliberationReportBuilder
                from trinity.workflow import WorkflowPersistence

                persistence = WorkflowPersistence(self.config.effective_state_dir)
                session = persistence.load()
                if session and session.goal:
                    structured = DeliberationReportBuilder(session, result=None).build()
                    report.apply_report(structured)
            except Exception:
                pass  # Fallback to snapshot rendering
        self.current_route = route
        self.switch_screen(route)

    def action_go_start(self) -> None:
        self.active_snapshot = None
        self.initial_prompt = None
        self.switch_to("start")

    def action_go_nexus(self) -> None:
        self.switch_to("nexus")

    def action_go_execution(self) -> None:
        self.switch_to("execution")

    def action_go_settings(self) -> None:
        self.switch_to("settings")

    def action_go_report(self) -> None:
        self.switch_to("report")

    def on_report_screen_export_requested(
        self,
        event: ReportScreen.ExportRequested,
    ) -> None:
        event.stop()
        snapshot = (
            event.snapshot
            or self.active_snapshot
            or self.snapshot_adapter.load_snapshot()
        )
        self._export_report_markdown(snapshot)

    def _export_report_markdown(self, snapshot: WorkflowNexusSnapshot) -> None:
        """Save a report as Markdown using the shared DeliberationReport builder."""
        from trinity.tui.report import DeliberationReportBuilder
        from trinity.workflow import WorkflowPersistence

        report_dir = self.config.effective_state_dir / "reports"
        filepath = unique_report_path(report_dir, snapshot.session_id)

        # Build from the full WorkflowSession for richer output
        persistence = WorkflowPersistence(self.config.effective_state_dir)
        session = persistence.load()
        if session is not None:
            builder = DeliberationReportBuilder(session, result=None)
            report = builder.build()
            markdown = report.to_markdown()
        elif snapshot_has_report_data(snapshot):
            markdown = snapshot_report_markdown(snapshot)
        else:
            self.notify(
                "No workflow data available to export.",
                title="Export Unavailable",
                severity="warning",
            )
            return

        filepath.write_text(markdown, encoding="utf-8")
        if self._screens_installed:
            self.get_screen("report", ReportScreen).show_export_path(filepath)
        self.notify(f"Report saved: {filepath}", title="Export Complete")


def run_textual_app(config: TrinityConfig) -> None:
    """Run the Textual workbench."""
    TrinityTextualApp(config).run()
