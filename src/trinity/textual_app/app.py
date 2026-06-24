"""Textual application shell for Trinity."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from inspect import Parameter, signature
from pathlib import Path
from typing import Literal

from textual.app import App
from textual.binding import Binding

from trinity import __version__
from trinity.config import TrinityConfig
from trinity.context.commands import (
    artifact_markdown,
    cleanup_oversized_backups_markdown,
    compact_memory_markdown,
    engine_from_config,
    memory_stats_markdown,
    memory_stats_rows,
    parse_oversized_cleanup_options,
)
from trinity.i18n import VALID_CAVEMAN_INTENSITIES
from trinity.providers.model_discovery import (
    ProviderModelChoice,
    discover_provider_models,
)
from trinity.slash_commands import (
    SESSION_ONLY_SETTING_NOTICE,
    parse_slash_command,
)
from trinity.textual_app import presenters as textual_presenters
from trinity.textual_app.presenters import NO_CURRENT_CONTEXT_MESSAGE
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
from trinity.textual_app.slash_palette import SlashCommandPaletteProvider
from trinity.textual_app.settings import UISettingsStore
from trinity.textual_app.snapshot import (
    LocalCommandSnapshot,
    NexusSnapshotAdapter,
    WORKFLOW_EVENT_DISPLAY_LIMIT,
    WorkflowNexusSnapshot,
)
from trinity.textual_app.i18n import localize_bindings
from trinity.textual_app.workflow_controller import (
    TextualWorkflowController,
    TextualWorkflowOutcome,
)
from trinity.textual_app.widgets.agent_recipient_model_selector import (
    AgentRecipientModelSelector,
)
from trinity.textual_app.widgets.confirm_quit_modal import ConfirmQuitModal
from trinity.textual_app.widgets.context_modal import ContextCommandModal
from trinity.textual_app.widgets.execution_retry_modal import (
    ExecutionRetryModal,
    ExecutionRetrySelection,
)
from trinity.textual_app.widgets.local_command_modal import LocalCommandModal
from trinity.textual_app.widgets.model_settings_modal import ModelSettingsModal
from trinity.textual_app.widgets.provider_inspector import ProviderInspector
from trinity.textual_app.widgets.resume_picker import ResumeWorkflowPicker
from trinity.textual_app.widgets.status_modal import StatusCommandModal
from trinity.textual_app.widgets.target_workspace_confirm_modal import (
    TargetWorkspaceConfirmModal,
)
from trinity.textual_app.widgets.workspace_picker import (
    WorkspacePicker,
    WorkspacePreflight,
    build_preflight,
    default_workspace_tree_root,
)
from trinity.tui.kitty_compat import install_textual_parser_patch

WorkbenchRoute = Literal["start", "nexus", "execution", "settings", "report"]


class TrinityTextualApp(App[None]):
    """Desktop-style Textual workbench for Trinity."""

    TITLE = "Trinity"
    SUB_TITLE = f"v{__version__}"
    COMMANDS = App.COMMANDS | {SlashCommandPaletteProvider}
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+n", "go_start", "New Session"),
        Binding("ctrl+1", "go_start", "Start"),
        Binding("ctrl+2", "go_nexus", "Nexus"),
        Binding("ctrl+3", "go_execution", "Execute"),
        Binding("ctrl+4", "go_report", "Report"),
        Binding("ctrl+comma", "go_settings", "Settings"),
    ]

    LOCALIZED_BINDINGS = {
        ("ctrl+q", "quit"): ("binding_quit", None),
        ("ctrl+n", "go_start"): ("binding_new_session", None),
        ("ctrl+1", "go_start"): ("binding_start", None),
        ("ctrl+2", "go_nexus"): ("binding_nexus", None),
        ("ctrl+3", "go_execution"): ("binding_execute", None),
        ("ctrl+comma", "go_settings"): ("binding_settings", None),
        ("ctrl+p", "command_palette"): ("binding_palette", "binding_palette_tooltip"),
    }

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

    #resume-picker {
        width: 112;
        max-width: 94%;
        height: 30;
        max-height: 88%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }

    #resume-picker-title {
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
    }

    .resume-archive-option {
        width: 100%;
        margin-bottom: 1;
    }

    #resume-archive-list {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
        margin-bottom: 1;
    }

    .resume-archive-option-selected {
        color: $accent;
        text-style: bold;
    }

    #cancel-resume-picker {
        width: 18;
    }

    #start-screen {
        width: 100%;
        height: 1fr;
        align: center middle;
        padding: 1 2;
    }

    #start-shell {
        width: 96;
        max-width: 96%;
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

    .agent-recipient-selector {
        width: 100%;
        height: auto;
        margin-top: 1;
        align-vertical: middle;
    }

    .recipient-label {
        width: auto;
        min-width: 10;
        content-align: left middle;
        color: $text-muted;
        margin-right: 1;
        height: 1;
    }

    .recipient-agent-toggle {
        width: 14;
        height: 1;
        margin-right: 1;
        padding: 0 1;
        content-align: left middle;
        background: $surface;
        color: $text-muted;
    }

    .recipient-agent-toggle:hover,
    .recipient-agent-toggle:focus {
        background-tint: $foreground 5%;
        color: $text;
    }

    .recipient-agent-toggle-selected {
        color: $accent;
        text-style: bold;
    }

    .recipient-agent-toggle-disabled {
        color: $text-muted;
        text-style: dim;
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
        height: 5;
        layout: grid;
        grid-size: 3 1;
        grid-gutter: 1;
    }

    .provider-panel {
        height: 5;
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

    .provider-running {
        border: round $warning;
    }

    .provider-state-waiting {
        border: round $primary;
    }

    .provider-state-idle {
        border: round $secondary;
    }

    .provider-state-done {
        border: round $success;
    }

    .provider-state-issue {
        border: round $error;
    }

    .provider-state-off {
        border: round $secondary;
    }

    .provider-disabled {
        color: $text-muted;
    }

    .provider-heading {
        width: 100%;
        height: 1;
    }

    .provider-name {
        width: 1fr;
        text-style: bold;
    }

    .provider-meta {
        color: $text-muted;
    }

    .provider-status {
        width: auto;
        min-width: 5;
        content-align: right middle;
        text-style: bold;
        color: $accent;
    }

    .provider-state-running .provider-status {
        color: $warning;
    }

    .provider-state-waiting .provider-status {
        color: $primary;
    }

    .provider-state-idle .provider-status {
        color: $text-muted;
    }

    .provider-state-done .provider-status {
        color: $success;
    }

    .provider-state-issue .provider-status {
        color: $error;
    }

    .provider-summary {
        color: $text-muted;
        height: 1;
    }

    #central-agent {
        width: 1fr;
        height: 1fr;
        border: heavy white;
        padding: 1 2;
        overflow-y: auto;
    }

    #central-agent.central-running {
        border: heavy $warning;
    }

    #nexus-main {
        height: 1fr;
        margin: 1 0;
    }

    #nexus-center-stack {
        width: 1fr;
        height: 1fr;
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

    #central-local-command-tables {
        height: auto;
        margin-top: 1;
    }

    .local-command-table-title {
        text-style: bold;
        color: $accent;
        margin-top: 1;
    }

    .local-command-table {
        height: auto;
        margin-bottom: 1;
    }

    #status-command-modal {
        width: 88;
        max-width: 95%;
        height: auto;
        max-height: 85%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }

    #status-command-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #status-command-body {
        margin-bottom: 1;
    }

    #status-command-table {
        height: auto;
        margin-bottom: 1;
    }

    #context-command-modal {
        width: 88;
        max-width: 95%;
        height: auto;
        max-height: 85%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }

    #context-command-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #context-command-body {
        height: auto;
        max-height: 24;
        margin-bottom: 1;
    }

    #local-command-modal {
        width: 92;
        max-width: 95%;
        height: auto;
        max-height: 85%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }

    #local-command-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #local-command-body {
        height: auto;
        max-height: 22;
        margin-bottom: 1;
    }

    #local-command-table {
        height: auto;
        margin-bottom: 1;
    }

    #local-command-hint {
        color: $text-muted;
        margin-bottom: 1;
    }

    #central-question-title {
        text-style: bold;
        color: $warning;
    }

    #central-action-title {
        text-style: bold;
        color: $warning;
        margin-top: 1;
    }

    #central-actions {
        layout: grid;
        grid-size: 2;
        grid-gutter: 1;
        height: auto;
        margin-bottom: 1;
    }

    #central-actions Button {
        width: 100%;
    }

    #nexus-question-panel {
        width: 100%;
        height: 11;
        max-height: 14;
        border: round $warning;
        margin-top: 1;
        padding: 0 1;
    }

    #nexus-question-panel.question-panel-empty {
        height: 3;
        border: round $primary;
    }

    #question-panel-title {
        text-style: bold;
        color: $warning;
        height: 1;
        margin-bottom: 1;
    }

    #question-panel-body {
        height: auto;
    }

    .question-empty {
        color: $text-muted;
    }

    .question-text {
        margin-top: 1;
    }

    .question-open {
        text-style: bold;
    }

    .question-answer {
        color: $success;
        margin-left: 2;
        margin-bottom: 1;
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
        width: 12;
        margin-left: 1;
    }

    #select-workspace {
        width: 20;
        margin-left: 1;
    }

    #nexus-target-workspace {
        width: 1fr;
        height: 3;
        margin-left: 2;
        content-align: left bottom;
        color: $text-muted;
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

    .settings-section-title {
        text-style: bold;
        color: $warning;
        margin-top: 1;
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
        height: 10;
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
        height: 36;
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

    #workspace-picker-bottom {
        height: auto;
        margin-top: 1;
    }

    #workspace-tree-actions {
        width: 1fr;
        height: auto;
    }

    #workspace-preflight {
        width: 38;
        height: 1fr;
        margin-left: 1;
        border: round $secondary;
        padding: 1;
    }

    #workspace-create-prompt {
        width: 64;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }

    #workspace-picker-actions {
        width: 38;
        height: auto;
        margin-left: 1;
        align-horizontal: right;
    }

    #workspace-picker-status {
        height: 1;
        margin-top: 1;
    }

    #execution-screen {
        width: 100%;
        height: 1fr;
        padding: 1;
    }

    #execution-header-row {
        height: 1;
    }

    #execution-header {
        height: 1;
        width: 1fr;
        text-style: bold;
        color: $accent;
    }

    #toggle-task-expanded {
        width: 16;
        margin-left: 1;
    }

    #execution-summary {
        height: 1;
        margin-top: 1;
        color: $text-muted;
    }

    #execution-package-list {
        height: 13;
        margin-top: 1;
        border: round $primary;
        padding: 0 1;
    }

    .execution-task-expanded #execution-package-list {
        height: 1fr;
    }

    .execution-package-header {
        height: 2;
        color: $text-muted;
    }

    .execution-package-row {
        height: 2;
    }

    .execution-package-lines {
        width: 100%;
        height: 2;
    }

    .execution-package-primary,
    .execution-package-secondary {
        width: 100%;
        height: 1;
    }

    .execution-package-task {
        width: 1fr;
    }

    .execution-task-expanded .execution-package-task {
        width: 1fr;
    }

    .execution-package-assignee {
        width: 20;
        color: $text-muted;
    }

    .execution-package-executor {
        width: 20;
    }

    .execution-package-status {
        width: 8;
        text-style: bold;
    }

    .execution-package-review {
        width: 22;
        color: $text-muted;
    }

    .execution-package-risk {
        width: 16;
        color: $text-muted;
    }

    .execution-package-spec {
        width: 8;
    }

    .execution-package-empty {
        color: $text-muted;
    }

    #execution-log {
        height: 9;
        border: round $primary;
        margin-top: 1;
        padding: 0 1;
    }

    .execution-task-expanded #execution-log {
        height: 6;
    }

    #execution-retry-modal {
        width: 108;
        max-width: 96%;
        height: 34;
        max-height: 92%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }

    #execution-retry-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #execution-retry-summary {
        color: $text-muted;
        margin-bottom: 1;
    }

    #execution-retry-filters {
        height: auto;
        margin-bottom: 1;
    }

    #execution-retry-filters Button {
        width: 16;
        margin-right: 1;
    }

    #execution-retry-list {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
    }

    #execution-retry-header {
        height: 1;
        color: $text-muted;
    }

    .retry-row {
        height: 1;
    }

    .retry-id {
        width: 8;
    }

    .retry-status {
        width: 11;
    }

    .retry-topic {
        width: 30;
    }

    .retry-owner {
        width: 11;
    }

    .retry-executor {
        width: 13;
    }

    .retry-note {
        width: 1fr;
        color: $text-muted;
    }

    #execution-retry-selected {
        height: 1;
        margin-top: 1;
        color: $text-muted;
    }

    #execution-retry-actions {
        height: auto;
        align-horizontal: right;
    }

    #work-package-detail-modal {
        width: 96;
        max-width: 94%;
        height: 34;
        max-height: 92%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }

    #work-package-detail-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #work-package-detail-body {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
        margin-bottom: 1;
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

    def __init__(
        self,
        config: TrinityConfig,
        workflow_controller: TextualWorkflowController | None = None,
        launch_cwd: Path | None = None,
    ) -> None:
        install_textual_parser_patch()
        super().__init__()
        localize_bindings(self._bindings, config.lang, self.LOCALIZED_BINDINGS)
        self.config = config
        self.current_route: WorkbenchRoute = "start"
        self.initial_prompt: str | None = None
        self.launch_cwd = self._default_launch_cwd(launch_cwd)
        self.workspace_candidate: Path | None = self.launch_cwd
        self.snapshot_adapter = NexusSnapshotAdapter(config)
        self.active_snapshot: WorkflowNexusSnapshot | None = None
        self.settings_store = UISettingsStore(config.effective_state_dir)
        self.confirmed_preflight: WorkspacePreflight | None = None
        self.workflow_controller = workflow_controller or TextualWorkflowController(config)
        self._screens_installed = False
        self._workflow_polling_started = False
        self._model_discovery_started = False
        self._agent_model_choices: dict[str, tuple[ProviderModelChoice, ...]] = {}
        self._local_command_results: list[LocalCommandSnapshot] = []
        self._pending_execute_retry: ExecutionRetrySelection | None = None

    def on_mount(self) -> None:
        self._install_workbench_screens()
        self.current_route = "start"
        self.push_screen("start")
        self._start_model_discovery()

    def _install_workbench_screens(self) -> None:
        if self._screens_installed:
            return

        self.install_screen(
            StartScreen(
                self.config,
                self.workspace_candidate,
                lang=self.config.lang,
            ),
            "start",
        )
        self.install_screen(NexusScreen(self.config), "nexus")
        self.install_screen(
            SettingsScreen(self.settings_store, self.config, lang=self.config.lang),
            "settings",
        )
        self.install_screen(ExecutionMatrixScreen(), "execution")
        self.install_screen(ReportScreen(), "report")

        self._screens_installed = True
        self._sync_nexus_workspace_candidate()

    def _start_model_discovery(self) -> None:
        if self._model_discovery_started:
            return
        self._model_discovery_started = True
        self.run_worker(
            self._discover_provider_models,
            name="provider-model-discovery",
            group="provider-model-discovery",
            exit_on_error=False,
            thread=True,
        )

    def _refresh_provider_models(self, *, use_cache: bool) -> None:
        self.run_worker(
            lambda: self._discover_provider_models(use_cache=use_cache),
            name="provider-model-discovery-refresh",
            group="provider-model-discovery",
            exit_on_error=False,
            thread=True,
        )

    def _discover_provider_models(self, *, use_cache: bool = True) -> None:
        agent_specs = list(self.config.agents.items())
        if not agent_specs:
            return

        max_workers = min(len(agent_specs), 8)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    discover_provider_models,
                    spec.provider,
                    spec.cli_command,
                    timeout_seconds=10.0,
                    use_cache=use_cache,
                ): name
                for name, spec in agent_specs
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    choices = future.result()
                except Exception:
                    choices = []
                if choices:
                    self.call_from_thread(
                        self._apply_discovered_model_choices,
                        {name: tuple(choices)},
                    )

    def _apply_discovered_model_choices(
        self,
        choices_by_agent: dict[str, tuple[ProviderModelChoice, ...]],
    ) -> None:
        self._agent_model_choices.update(choices_by_agent)
        for screen_name, screen_type in (
            ("start", StartScreen),
            ("nexus", NexusScreen),
        ):
            screen = self.get_screen(screen_name, screen_type)
            screen.set_agent_model_choices(choices_by_agent)
        if isinstance(self.screen, ModelSettingsModal):
            self.screen.set_model_choices(choices_by_agent)

    def on_start_screen_submitted(self, event: StartScreen.Submitted) -> None:
        event.stop()
        self.initial_prompt = event.prompt
        if self.workspace_candidate is None:
            self.workspace_candidate = event.workspace_candidate
        nexus = self.get_screen("nexus", NexusScreen)
        nexus.set_initial_prompt(event.prompt)
        nexus.set_agent_selection(event.target_agents, event.agent_model_overrides)
        self._sync_nexus_workspace_candidate()
        target_workspace = self._safe_start_target_workspace(self.workspace_candidate)
        start_kwargs = {
            "target_workspace": target_workspace,
            "target_agents": event.target_agents,
            "agent_model_overrides": event.agent_model_overrides,
        }
        outcome = self._call_controller_method(
            self.workflow_controller.start_prompt,
            event.prompt,
            **start_kwargs,
        )
        self._remember_confirmed_target_preflight(target_workspace, outcome.snapshot)
        self._apply_workflow_outcome(outcome)
        self.switch_to("nexus")

    def on_start_screen_slash_command_submitted(
        self,
        event: StartScreen.SlashCommandSubmitted,
    ) -> None:
        event.stop()
        self._handle_textual_slash_command(event.text)

    def on_start_screen_workspace_requested(
        self,
        event: StartScreen.WorkspaceRequested,
    ) -> None:
        event.stop()
        self._open_workspace_picker(
            WorkflowNexusSnapshot(),
            self._on_workspace_candidate_selected,
            intent="select",
        )

    def on_nexus_screen_follow_up_submitted(
        self,
        event: NexusScreen.FollowUpSubmitted,
    ) -> None:
        event.stop()
        outcome = self._call_controller_method(
            self.workflow_controller.submit_follow_up,
            event.text,
            target_agents=event.target_agents,
            agent_model_overrides=event.agent_model_overrides,
        )
        self._apply_workflow_outcome(outcome)
        if outcome.target_workspace_required:
            self._open_execute_workspace_picker(outcome.snapshot)

    @staticmethod
    def _call_controller_method(method, *args, **kwargs):
        """Call a controller method while tolerating older test doubles."""
        try:
            parameters = signature(method).parameters
        except (TypeError, ValueError):
            return method(*args, **kwargs)

        accepts_kwargs = any(
            parameter.kind == Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
        if accepts_kwargs:
            return method(*args, **kwargs)

        supported_kwargs = {
            key: value
            for key, value in kwargs.items()
            if key in parameters
        }
        return method(*args, **supported_kwargs)

    def on_nexus_screen_slash_command_submitted(
        self,
        event: NexusScreen.SlashCommandSubmitted,
    ) -> None:
        event.stop()
        self._handle_textual_slash_command(event.text)

    def on_nexus_screen_question_answered(
        self,
        event: NexusScreen.QuestionAnswered,
    ) -> None:
        event.stop()
        outcome = self.workflow_controller.answer_question(
            event.answer.question_id, event.answer.answer
        )
        self._apply_workflow_outcome(outcome)

    def on_nexus_screen_inspector_requested(
        self,
        event: NexusScreen.InspectorRequested,
    ) -> None:
        event.stop()
        snapshot = (
            event.snapshot
            or self.active_snapshot
            or self.workflow_controller.snapshot()
            or self.snapshot_adapter.load_snapshot()
        )
        self.push_screen(ProviderInspector(snapshot.providers, lang=self.config.lang))

    def on_nexus_screen_execute_requested(
        self,
        event: NexusScreen.ExecuteRequested,
    ) -> None:
        event.stop()
        outcome = self.workflow_controller.request_execution()
        self._apply_workflow_outcome(outcome)
        if outcome.execution_recovery_required:
            self._present_execution_recovery(
                "/execute",
                outcome.snapshot,
                outcome.message,
            )
            return
        if outcome.target_workspace_required:
            self._open_execute_workspace_picker(outcome.snapshot)

    def on_nexus_screen_workspace_requested(
        self,
        event: NexusScreen.WorkspaceRequested,
    ) -> None:
        event.stop()
        snapshot = (
            event.snapshot
            or self.active_snapshot
            or self.workflow_controller.snapshot()
            or self.snapshot_adapter.load_snapshot()
        )
        self._open_workspace_picker(
            snapshot,
            self._on_nexus_workspace_selected,
            intent="select",
        )

    def on_execution_matrix_screen_retry_requested(
        self,
        event: ExecutionMatrixScreen.RetryRequested,
    ) -> None:
        event.stop()
        selector = "all"
        package_ids: list[str] = []
        self.workflow_controller.preview_execution_retry(selector, package_ids)
        snapshot = self.workflow_controller.snapshot() or event.snapshot
        self._apply_workflow_outcome(TextualWorkflowOutcome(snapshot))
        if not snapshot.work_package_details:
            self.notify(
                "No work packages are available in the current workflow.",
                severity="warning",
            )
            return
        self.push_screen(
            ExecutionRetryModal(
                snapshot,
                selector=selector,
                package_ids=tuple(package_ids),
                lang=self.config.lang,
            ),
            self._on_execute_retry_selected,
        )

    def on_nexus_screen_repair_action_requested(
        self,
        event: NexusScreen.RepairActionRequested,
    ) -> None:
        event.stop()
        self._handle_review_repair_action(event.action, event.snapshot)

    def _handle_review_repair_action(
        self,
        action: str,
        snapshot: WorkflowNexusSnapshot | None,
    ) -> None:
        current = snapshot or self._fresh_textual_snapshot()
        package_ids = self._review_repair_blocked_ids(current)
        if action == "repair-open-review":
            self._present_review_repair_details(current)
            return
        if action == "repair-retry-once":
            outcome = self.workflow_controller.retry_blocked_review_repairs()
            if outcome.target_workspace_required:
                self._pending_execute_retry = ExecutionRetrySelection(
                    "custom",
                    package_ids,
                )
                self._apply_workflow_outcome(outcome)
                self._open_execute_workspace_picker(outcome.snapshot)
                return
            self._apply_workflow_outcome(outcome)
            if outcome.execution_requested:
                execution = self.get_screen("execution", ExecutionMatrixScreen)
                execution.apply_execution_state(self.confirmed_preflight, outcome.snapshot)
                self.switch_to("execution")
            return
        if action == "repair-mark-done":
            self._apply_workflow_outcome(
                self.workflow_controller.accept_blocked_review_repairs()
            )
            return
        if action == "repair-stop":
            self._apply_workflow_outcome(
                self.workflow_controller.stop_blocked_review_repairs()
            )
            return

    def _open_execute_workspace_picker(self, snapshot: WorkflowNexusSnapshot) -> None:
        self._open_workspace_picker(snapshot, self._on_workspace_preflight)

    def _open_workspace_picker(
        self,
        snapshot: WorkflowNexusSnapshot,
        callback,
        *,
        intent: str = "execute",
    ) -> None:
        self.push_screen(
            WorkspacePicker(
                candidate=self.workspace_candidate,
                lang=self.config.lang,
                snapshot=snapshot,
                cwd=self.config.project_dir,
                tree_root=default_workspace_tree_root(self.config.project_dir),
                intent=intent,
            ),
            callback,
        )

    def _on_workspace_candidate_selected(
        self,
        preflight: WorkspacePreflight | None,
    ) -> None:
        if preflight is None:
            return
        self.workspace_candidate = preflight.path
        start = self.get_screen("start", StartScreen)
        start.set_workspace_candidate(preflight.path)
        self._sync_nexus_workspace_candidate()

    def _on_nexus_workspace_selected(
        self,
        preflight: WorkspacePreflight | None,
    ) -> None:
        if preflight is None:
            return
        if self._is_control_repo_target(preflight.path):
            self.push_screen(
                TargetWorkspaceConfirmModal(
                    target_path=preflight.path,
                    control_repo=self.config.project_dir,
                ),
                lambda confirmed: self._on_nexus_workspace_selected_confirmed(
                    preflight,
                    confirmed,
                ),
            )
            return
        self._continue_nexus_workspace_selection(
            preflight,
            control_repo_confirmed=False,
        )

    def _on_nexus_workspace_selected_confirmed(
        self,
        preflight: WorkspacePreflight,
        confirmed: bool | None,
    ) -> None:
        if confirmed:
            self._continue_nexus_workspace_selection(
                preflight,
                control_repo_confirmed=True,
            )
            return
        self._record_slash_command_result(
            "/target",
            "Target",
            "Target workspace selection cancelled.",
            severity="warning",
            empty=True,
            action_hint="Choose a workspace outside the Trinity control repo.",
        )

    def _continue_nexus_workspace_selection(
        self,
        preflight: WorkspacePreflight,
        *,
        control_repo_confirmed: bool,
    ) -> None:
        self.workspace_candidate = preflight.path
        self._set_textual_target_workspace(
            preflight.path,
            control_repo_confirmed=control_repo_confirmed,
        )
        self._sync_nexus_workspace_candidate()

    def _safe_start_target_workspace(self, path: Path | None) -> Path | None:
        """Return a start-screen target that can be persisted without confirmation."""
        if path is None:
            return None
        if self._is_control_repo_target(path):
            return None
        return path

    @staticmethod
    def _default_launch_cwd(launch_cwd: Path | None = None) -> Path:
        """Return the directory Trinity was launched from for target defaults."""
        try:
            return (launch_cwd or Path.cwd()).expanduser().resolve()
        except OSError:
            return (launch_cwd or Path.cwd()).expanduser()

    def _remember_confirmed_target_preflight(
        self,
        path: Path | None,
        snapshot: WorkflowNexusSnapshot,
    ) -> None:
        """Keep Execution Matrix workspace header aligned with persisted target."""
        if path is None:
            self.confirmed_preflight = None
            return
        self.confirmed_preflight = build_preflight(path, snapshot)

    def _on_workspace_preflight(self, preflight: WorkspacePreflight | None) -> None:
        if preflight is None:
            self._pending_execute_retry = None
            return
        if self._is_control_repo_target(preflight.path):
            self.push_screen(
                TargetWorkspaceConfirmModal(
                    target_path=preflight.path,
                    control_repo=self.config.project_dir,
                ),
                lambda confirmed: self._on_workspace_preflight_confirmed(
                    preflight,
                    confirmed,
                ),
            )
            return
        self._continue_workspace_preflight(
            preflight,
            control_repo_confirmed=False,
        )

    def _on_workspace_preflight_confirmed(
        self,
        preflight: WorkspacePreflight,
        confirmed: bool | None,
    ) -> None:
        if confirmed:
            self._continue_workspace_preflight(
                preflight,
                control_repo_confirmed=True,
            )
            return
        self._record_slash_command_result(
            "/target",
            "Target",
            "Workspace preflight cancelled.",
            severity="warning",
            empty=True,
            action_hint="Choose a workspace outside the Trinity control repo.",
        )
        self._pending_execute_retry = None

    def _continue_workspace_preflight(
        self,
        preflight: WorkspacePreflight,
        *,
        control_repo_confirmed: bool,
    ) -> None:
        self.confirmed_preflight = preflight
        self.workflow_controller.set_target_workspace(
            preflight.path,
            control_repo_confirmed=control_repo_confirmed,
        )
        pending_retry = self._pending_execute_retry
        self._pending_execute_retry = None
        if pending_retry is not None:
            outcome = self.workflow_controller.confirm_execution_retry(
                pending_retry.selector,
                list(pending_retry.package_ids),
            )
        else:
            outcome = self.workflow_controller.request_execution()
        self._apply_workflow_outcome(outcome)
        if outcome.execution_recovery_required:
            self._present_execution_recovery(
                "/execute",
                outcome.snapshot,
                outcome.message,
            )
            return
        snapshot = outcome.snapshot
        execution = self.get_screen("execution", ExecutionMatrixScreen)
        execution.apply_execution_state(preflight, snapshot)
        self.switch_to("execution")

    def _ensure_workflow_polling(self) -> None:
        if self._workflow_polling_started:
            return
        self._workflow_polling_started = True
        self.set_interval(0.25, self._poll_workflow_controller, name="workflow-poll")

    def _poll_workflow_controller(self) -> None:
        outcome = self.workflow_controller.drain_updates()
        if outcome is not None:
            self._apply_workflow_outcome(outcome)
            if outcome.target_workspace_required:
                self._open_execute_workspace_picker(outcome.snapshot)
        elif getattr(self.workflow_controller, "is_running", False):
            self._advance_activity_frame()

    def _apply_workflow_outcome(self, outcome: TextualWorkflowOutcome) -> None:
        snapshot = self._with_local_command_results(outcome.snapshot)
        self.active_snapshot = snapshot
        if self._screens_installed and self.current_route == "nexus":
            nexus = self.get_screen("nexus", NexusScreen)
            nexus.apply_snapshot(snapshot)
            if outcome.running:
                nexus.advance_activity_frame()
        if self.current_route == "execution" and self.confirmed_preflight is not None:
            execution = self.get_screen("execution", ExecutionMatrixScreen)
            execution.apply_execution_state(self.confirmed_preflight, snapshot)
        if outcome.message:
            self.notify(outcome.message)
        if outcome.running:
            self._ensure_workflow_polling()

    def _handle_textual_slash_command(self, text: str) -> None:
        """Execute a Trinity slash command without routing it as model input."""
        parsed = parse_slash_command(text)
        if parsed is None:
            return
        if parsed.error:
            self._record_slash_command_result(
                text,
                "Syntax Error",
                parsed.error,
                severity="warning",
            )
            return
        if not parsed.token:
            return
        if parsed.spec is None:
            suggestions = self._slash_command_suggestions(parsed.token)
            self._record_slash_command_result(
                parsed.token,
                "Unknown Command",
                self._unknown_command_markdown(parsed.token, suggestions),
                severity="warning",
                table_columns=("Suggestion", "Summary"),
                table_rows=self._unknown_command_rows(suggestions),
            )
            return

        command = parsed.command_id
        args = list(parsed.args)

        if command in {"quit", "exit", "q"}:
            self.push_screen(
                ConfirmQuitModal(
                    running=bool(getattr(self.workflow_controller, "is_running", False))
                ),
                self._on_quit_confirmed,
            )
            return
        if command == "help":
            self._record_slash_command_result(
                parsed.spec.name,
                "Trinity Commands",
                self._help_markdown(),
                table_columns=("Command", "Category", "Agent Call", "Summary"),
                table_rows=self._help_rows(),
            )
            return
        if command == "status":
            snapshot = self._current_textual_snapshot()
            self._show_textual_status(parsed.spec.name, snapshot)
            return
        if command == "workflow":
            snapshot = self._refresh_textual_snapshot()
            self._record_slash_command_result(
                parsed.spec.name,
                "Workflow",
                self._snapshot_workflow_markdown(snapshot),
                table_columns=("Item", "Value"),
                table_rows=self._snapshot_workflow_rows(snapshot),
            )
            return
        if command == "questions":
            snapshot = self._refresh_textual_snapshot()
            select_requested = any(arg.lower() in {"--select", "-s"} for arg in args)
            has_questions = bool(snapshot.questions)
            self._record_slash_command_result(
                parsed.spec.name,
                "Questions",
                self._questions_select_markdown(snapshot)
                if select_requested
                else self._questions_markdown(snapshot),
                empty=not has_questions,
                action_hint=(
                    "Use question panel buttons or `/answer <id|index|next> <answer>`."
                    if has_questions
                    else "Continue planning until the central agent raises a question."
                ),
                table_columns=("ID", "Status", "Question", "Options"),
                table_rows=self._questions_rows(snapshot),
            )
            return
        if command == "decisions":
            snapshot = self._refresh_textual_snapshot()
            has_decisions = bool(snapshot.decisions)
            self._record_slash_command_result(
                parsed.spec.name,
                "Decisions",
                self._decisions_markdown(snapshot),
                empty=not has_decisions,
                action_hint=(
                    "Answer pending questions with `/answer` to add decisions."
                    if not has_decisions
                    else ""
                ),
                table_columns=("#", "Decision"),
                table_rows=self._decisions_rows(snapshot),
            )
            return
        if command == "packages":
            snapshot = self._refresh_textual_snapshot()
            has_packages = bool(snapshot.work_packages or snapshot.central_work_packages)
            self._record_slash_command_result(
                parsed.spec.name,
                "Packages",
                self._packages_markdown(snapshot),
                empty=not has_packages,
                action_hint=(
                    "Finish planning until a blueprint or local WP graph is generated."
                    if not has_packages
                    else ""
                ),
                table_columns=("#", "Source", "Package"),
                table_rows=self._packages_rows(snapshot),
            )
            return
        if command == "subtasks":
            snapshot = self._refresh_textual_snapshot()
            has_subtasks = bool(snapshot.subtasks)
            self._record_slash_command_result(
                parsed.spec.name,
                "Subtasks",
                self._subtasks_markdown(snapshot),
                empty=not has_subtasks,
                action_hint=(
                    "Subtasks appear after an executing provider reports delegated work."
                    if not has_subtasks
                    else ""
                ),
                table_columns=("ID", "Package", "Delegated To", "Status", "Summary"),
                table_rows=self._subtasks_rows(snapshot),
            )
            return
        if command == "context":
            self._handle_textual_context_command(parsed.spec.name)
            return
        if command == "model":
            self._open_model_settings_modal()
            return
        if command == "memory":
            self._handle_textual_memory_command(args)
            return
        if command == "artifact":
            self._handle_textual_artifact_command(args)
            return
        if command == "history":
            snapshot = self._refresh_textual_snapshot()
            history_rows = self._history_rows(snapshot)
            self._record_slash_command_result(
                parsed.spec.name,
                "History",
                self._history_markdown(snapshot, history_rows),
                empty=not history_rows,
                action_hint=(
                    "Run a prompt, execute a workflow, or use local slash commands first."
                    if not history_rows
                    else ""
                ),
                table_columns=("Kind", "Item"),
                table_rows=history_rows,
            )
            return
        if command == "report":
            self._handle_textual_report_command(args)
            return
        if command == "rounds":
            self._handle_textual_rounds_command(parsed.spec.name, args)
            return
        if command == "agent":
            self._handle_textual_agent_command(parsed.spec.name, args)
            return
        if command == "caveman":
            self._handle_textual_caveman_command(parsed.spec.name, args)
            return
        if command == "save":
            self._record_slash_command_result(
                parsed.spec.name,
                "Save",
                "Textual workflows are persisted automatically. Use /report save for Markdown export.",
            )
            return
        if command == "target":
            self._handle_textual_target_command(args)
            return
        if command == "resume":
            self._handle_textual_resume_command(args)
            return
        if command == "answer":
            self._handle_textual_answer_command(args)
            return
        if command == "ask":
            self._handle_textual_ask_command(parsed.spec.name, args)
            return
        if command == "execute-retry":
            self._handle_textual_execute_retry_command(args)
            return
        if command == "review":
            outcome = self.workflow_controller.request_review(args)
            message = outcome.message
            if message:
                outcome = replace(outcome, message="")
            self._apply_workflow_outcome(outcome)
            if message:
                self._record_slash_command_result(
                    parsed.spec.name,
                    "Review",
                    message,
                    severity=(
                        "warning"
                        if message.startswith("No review") or "not connected" in message
                        else "info"
                    ),
                    table_columns=("Item", "Value"),
                    table_rows=self._review_rows(outcome.snapshot),
                    action_hint="Run `/review wp`, `/review final`, or `/review all`.",
                )
            return
        if command == "improve":
            outcome = self.workflow_controller.request_improvement(args)
            message = outcome.message
            if message:
                outcome = replace(outcome, message="")
            self._apply_workflow_outcome(outcome)
            if message:
                self._record_slash_command_result(
                    parsed.spec.name,
                    "Improve",
                    message,
                    severity=(
                        "warning"
                        if message.startswith("No matching")
                        or "required" in message
                        else "info"
                    ),
                    table_columns=("Item", "Value"),
                    table_rows=self._improve_rows(outcome.snapshot),
                    action_hint="Use `/improve high`, `/improve all`, `/improve AI-001`, or `/improve done`.",
                )
            return
        if command == "execute":
            outcome = self.workflow_controller.request_execution(" ".join(args))
            message = outcome.message
            if message:
                outcome = replace(outcome, message="")
            self._apply_workflow_outcome(outcome)
            if outcome.execution_recovery_required:
                self._present_execution_recovery(
                    parsed.spec.name,
                    outcome.snapshot,
                    message,
                )
                return
            if message:
                self._record_slash_command_result(
                    parsed.spec.name,
                    "Execute",
                    message,
                    severity="warning",
                    empty=True,
                    action_hint=("Finish planning first, then run `/execute` from Nexus."),
                )
            if outcome.target_workspace_required:
                self._open_execute_workspace_picker(outcome.snapshot)
            return

    def _handle_textual_ask_command(self, command_name: str, args: list[str]) -> None:
        target_agents, model_overrides, prompt, error = self._parse_ask_args(args)
        if error:
            self._record_slash_command_result(
                command_name,
                "Ask",
                error,
                severity="warning",
                empty=True,
                action_hint="/ask <all|agent[,agent...]> [--model MODEL] <prompt>",
            )
            return

        if self.current_route == "start":
            self.initial_prompt = prompt
            nexus = self.get_screen("nexus", NexusScreen)
            nexus.set_initial_prompt(prompt)
            nexus.set_agent_selection(target_agents, model_overrides)
            target_workspace = self._safe_start_target_workspace(self.workspace_candidate)
            outcome = self.workflow_controller.start_prompt(
                prompt,
                target_workspace=target_workspace,
                target_agents=target_agents,
                agent_model_overrides=model_overrides,
            )
            self._remember_confirmed_target_preflight(target_workspace, outcome.snapshot)
            self._apply_workflow_outcome(outcome)
            self.switch_to("nexus")
            return

        nexus = self.get_screen("nexus", NexusScreen)
        nexus.set_agent_selection(target_agents, model_overrides)
        outcome = self.workflow_controller.submit_follow_up(
            prompt,
            target_agents=target_agents,
            agent_model_overrides=model_overrides,
        )
        self._apply_workflow_outcome(outcome)
        if outcome.target_workspace_required:
            self._open_execute_workspace_picker(outcome.snapshot)

    def _parse_ask_args(
        self,
        args: list[str],
    ) -> tuple[tuple[str, ...], dict[str, str], str, str]:
        if not args:
            return (), {}, "", "Usage: /ask <all|agent[,agent...]> [--model MODEL] <prompt>"

        active_agents = tuple(self.config.active_agents.keys())
        selector = args[0].strip().lower()
        if selector == "all":
            target_agents = active_agents
        else:
            requested = tuple(
                item.strip().lower()
                for item in selector.split(",")
                if item.strip()
            )
            unknown = [name for name in requested if name not in self.config.active_agents]
            if unknown:
                return (), {}, "", f"Unknown or disabled agent: {', '.join(unknown)}"
            target_agents = requested

        if not target_agents:
            return (), {}, "", "No active agents are available for /ask."

        model = ""
        prompt_parts: list[str] = []
        index = 1
        while index < len(args):
            value = args[index]
            if value in {"--model", "-m"}:
                if index + 1 >= len(args):
                    return (), {}, "", "Missing model after --model."
                model = args[index + 1].strip()
                index += 2
                continue
            prompt_parts.append(value)
            index += 1

        prompt = " ".join(prompt_parts).strip()
        if not prompt:
            return (), {}, "", "Prompt cannot be empty."

        model_overrides = {agent: model for agent in target_agents} if model else {}
        return target_agents, model_overrides, prompt, ""

    def _on_quit_confirmed(self, confirmed: bool | None) -> None:
        if confirmed:
            self.exit()

    def _refresh_textual_snapshot(self) -> WorkflowNexusSnapshot:
        """Load and apply the current workflow snapshot."""
        snapshot = self._current_textual_snapshot()
        self._apply_workflow_outcome(TextualWorkflowOutcome(snapshot))
        return self.active_snapshot or snapshot

    def _current_textual_snapshot(self) -> WorkflowNexusSnapshot:
        """Return the current workflow snapshot without rendering it."""
        return (
            self.active_snapshot
            or self.workflow_controller.snapshot()
            or self.snapshot_adapter.load_snapshot()
        )

    def _fresh_textual_snapshot(self) -> WorkflowNexusSnapshot:
        """Return the latest persisted/controller snapshot, ignoring stale UI state."""
        return self.workflow_controller.snapshot() or self.snapshot_adapter.load_snapshot()

    def _refresh_current_route_from_active_snapshot(self) -> None:
        """Re-apply the active snapshot after Textual finishes a screen switch."""
        if not self._screens_installed:
            return
        snapshot = (
            self.active_snapshot
            or self.workflow_controller.snapshot()
            or self.snapshot_adapter.load_snapshot()
        )
        if self.current_route == "nexus":
            self._sync_nexus_workspace_candidate()
            self.get_screen("nexus", NexusScreen).apply_snapshot(snapshot)
        elif self.current_route == "execution" and self.confirmed_preflight is not None:
            self.get_screen("execution", ExecutionMatrixScreen).apply_execution_state(
                self.confirmed_preflight,
                snapshot,
            )
        elif self.current_route == "report":
            self.get_screen("report", ReportScreen).apply_snapshot(snapshot)

    def _with_local_command_results(
        self,
        snapshot: WorkflowNexusSnapshot,
    ) -> WorkflowNexusSnapshot:
        """Attach recent local slash command results to a snapshot."""
        return replace(
            snapshot,
            local_commands=list(self._local_command_results[-8:]),
        )

    def _record_slash_command_result(
        self,
        command: str,
        title: str,
        body: str,
        *,
        severity: str = "info",
        result_kind: str = "markdown",
        empty: bool = False,
        action_hint: str = "",
        table_columns: tuple[str, ...] = (),
        table_rows: tuple[tuple[str, ...], ...] = (),
        start_modal: bool = True,
    ) -> None:
        """Record a local slash command result in the central Textual view."""
        result = self._local_command_snapshot(
            command,
            title,
            body,
            severity=severity,
            result_kind=result_kind,
            empty=empty,
            action_hint=action_hint,
            table_columns=table_columns,
            table_rows=table_rows,
        )
        self._record_central_conversation_result(result)
        self._present_local_command_result(
            result,
            start_modal=start_modal,
            notify=True,
        )

    def _record_central_conversation_result(
        self,
        result: LocalCommandSnapshot,
    ) -> None:
        """Persist Textual central-panel command results for report export."""
        from trinity.workflow import WorkflowPersistence

        persistence = WorkflowPersistence(self.config.effective_state_dir)
        session = persistence.load()
        if session is None or not session.id:
            return
        persistence.append_event(
            {
                "timestamp": time.time(),
                "workflow_id": session.id,
                "event": "central_conversation_recorded",
                "state": session.state.value,
                "data": {
                    "message_id": f"cc-local-{int(time.time() * 1000)}",
                    "role": "tool",
                    "channel": "local_command",
                    "title": result.title,
                    "body": result.body,
                    "command": result.command,
                    "related_ids": [],
                    "truncated": False,
                },
            }
        )

    def _present_local_command_result(
        self,
        result: LocalCommandSnapshot,
        *,
        start_modal: bool = True,
        notify: bool = True,
    ) -> None:
        """Render a local slash command result on the active Textual surface."""
        self._replace_local_command_result(result)
        snapshot = self._with_local_command_results(self._current_textual_snapshot())
        self.active_snapshot = snapshot
        if self.current_route == "start" and start_modal:
            self.push_screen(LocalCommandModal(result))
        else:
            self._apply_workflow_outcome(TextualWorkflowOutcome(snapshot))
        if notify and self.current_route != "start":
            notify_severity = (
                "warning" if result.severity in {"warning", "error"} else "information"
            )
            self.notify(result.title, title="Slash Command", severity=notify_severity)

    def _show_textual_status(
        self,
        command: str,
        snapshot: WorkflowNexusSnapshot,
    ) -> None:
        """Show status in the surface appropriate for the current Textual route."""
        result = self._local_command_snapshot(
            command,
            "Status",
            self._snapshot_status_markdown(snapshot),
            table_columns=("Item", "Value"),
            table_rows=self._snapshot_status_rows(snapshot),
        )
        self._replace_local_command_result(result)
        snapshot = self._with_local_command_results(snapshot)
        self.active_snapshot = snapshot
        if self.current_route == "start":
            self.push_screen(StatusCommandModal(result))
            return
        self._apply_workflow_outcome(TextualWorkflowOutcome(snapshot))

    def _open_model_settings_modal(self) -> None:
        """Open the model settings modal for the active prompt selector."""
        selector = self._active_agent_selector()
        if selector is None:
            self.notify(
                "Model settings are available on Start and Nexus.",
                title="Model Settings",
                severity="warning",
            )
            return
        self._refresh_provider_models(use_cache=False)
        choices_by_agent = selector.model_choices_by_agent()
        choices_by_agent.update(self._agent_model_choices)
        self.push_screen(
            ModelSettingsModal(
                self.config.agents,
                choices_by_agent,
                selector.selected_models(),
                lang=self.config.lang,
            ),
            self._on_model_settings_applied,
        )

    def _on_model_settings_applied(
        self,
        selections: dict[str, str] | None,
    ) -> None:
        if selections is None:
            return
        selector = self._active_agent_selector()
        if selector is None:
            return
        selector.set_model_selections(selections)
        self.notify(
            "Model settings updated.",
            title="Model Settings",
        )

    def _active_agent_selector(self) -> AgentRecipientModelSelector | None:
        if self.current_route == "start":
            screen = self.get_screen("start", StartScreen)
        elif self.current_route == "nexus":
            screen = self.get_screen("nexus", NexusScreen)
        else:
            return None
        if not screen.is_mounted:
            return None
        return screen.query_one(AgentRecipientModelSelector)

    def _present_execution_recovery(
        self,
        command: str,
        snapshot: WorkflowNexusSnapshot,
        message: str = "",
    ) -> None:
        """Show interrupted execution recovery details as a local command result."""
        body_parts = [message.strip()] if message.strip() else []
        body_parts.append(self._execution_recovery_markdown(snapshot))
        self._record_slash_command_result(
            command,
            "Execution Recovery",
            "\n\n".join(body_parts),
            severity="warning",
            action_hint=("Use `/execute-retry`, `/execute mark-interrupted`, or `/execute abort`."),
            table_columns=("Item", "Value"),
            table_rows=self._execution_recovery_rows(snapshot),
            start_modal=False,
        )

    def _present_review_repair_details(self, snapshot: WorkflowNexusSnapshot) -> None:
        self._record_slash_command_result(
            "/review",
            "Review Repair",
            self._review_repair_details_markdown(snapshot),
            severity="warning",
            action_hint="Choose Retry once, Mark done, or Stop from the central panel.",
            table_columns=("WP", "Repair state"),
            table_rows=self._review_repair_rows(snapshot),
            start_modal=False,
        )

    @staticmethod
    def _review_repair_blocked_ids(
        snapshot: WorkflowNexusSnapshot,
    ) -> tuple[str, ...]:
        return textual_presenters.review_repair_blocked_ids(snapshot)

    @staticmethod
    def _review_repair_details_markdown(snapshot: WorkflowNexusSnapshot) -> str:
        return textual_presenters.review_repair_details_markdown(snapshot)

    @staticmethod
    def _review_repair_rows(
        snapshot: WorkflowNexusSnapshot,
    ) -> tuple[tuple[str, str], ...]:
        return textual_presenters.review_repair_rows(snapshot)

    @staticmethod
    def _execution_recovery_markdown(snapshot: WorkflowNexusSnapshot) -> str:
        return textual_presenters.execution_recovery_markdown(snapshot)

    @staticmethod
    def _execution_recovery_rows(
        snapshot: WorkflowNexusSnapshot,
    ) -> tuple[tuple[str, str], ...]:
        return textual_presenters.execution_recovery_rows(snapshot)

    def _local_command_snapshot(
        self,
        command: str,
        title: str,
        body: str,
        *,
        severity: str = "info",
        result_kind: str = "markdown",
        empty: bool = False,
        action_hint: str = "",
        table_columns: tuple[str, ...] = (),
        table_rows: tuple[tuple[str, ...], ...] = (),
    ) -> LocalCommandSnapshot:
        """Build a local slash command result snapshot."""
        return LocalCommandSnapshot(
            command=command,
            title=title,
            body=body.strip() or "(no output)",
            severity=severity,
            result_kind=result_kind,
            empty=empty,
            action_hint=action_hint,
            table_columns=table_columns,
            table_rows=table_rows,
        )

    def _replace_local_command_result(
        self,
        result: LocalCommandSnapshot,
    ) -> None:
        """Keep only the latest result for each local slash command."""
        self._local_command_results = [
            item for item in self._local_command_results if item.command != result.command
        ]
        self._local_command_results.append(result)

    @staticmethod
    def _snapshot_status_markdown(snapshot: WorkflowNexusSnapshot) -> str:
        return textual_presenters.snapshot_status_markdown(snapshot)

    @staticmethod
    def _snapshot_status_rows(
        snapshot: WorkflowNexusSnapshot,
    ) -> tuple[tuple[str, str], ...]:
        return textual_presenters.snapshot_status_rows(snapshot)

    @staticmethod
    def _readiness_label(readiness: str) -> str:
        return textual_presenters.readiness_label(readiness)

    @staticmethod
    def _slash_command_suggestions(token: str) -> tuple[str, ...]:
        return textual_presenters.slash_command_suggestions(token)

    @staticmethod
    def _unknown_command_markdown(token: str, suggestions: tuple[str, ...]) -> str:
        return textual_presenters.unknown_command_markdown(token, suggestions)

    @staticmethod
    def _unknown_command_rows(
        suggestions: tuple[str, ...],
    ) -> tuple[tuple[str, str], ...]:
        return textual_presenters.unknown_command_rows(suggestions)

    def _help_markdown(self) -> str:
        """Return registry-backed help text for Trinity-owned slash commands."""
        return textual_presenters.help_markdown()

    def _help_rows(self) -> tuple[tuple[str, str, str, str], ...]:
        """Return slash command registry rows for read-only help tables."""
        return textual_presenters.help_rows(use_korean=self.config.lang == "ko")

    @staticmethod
    def _snapshot_workflow_markdown(snapshot: WorkflowNexusSnapshot) -> str:
        return textual_presenters.snapshot_workflow_markdown(snapshot)

    @staticmethod
    def _snapshot_workflow_rows(
        snapshot: WorkflowNexusSnapshot,
    ) -> tuple[tuple[str, str], ...]:
        return textual_presenters.snapshot_workflow_rows(snapshot)

    @staticmethod
    def _snapshot_has_current_context(snapshot: WorkflowNexusSnapshot) -> bool:
        return textual_presenters.snapshot_has_current_context(snapshot)

    @staticmethod
    def _snapshot_context_markdown(snapshot: WorkflowNexusSnapshot) -> str:
        return textual_presenters.snapshot_context_markdown(snapshot)

    @staticmethod
    def _questions_markdown(snapshot: WorkflowNexusSnapshot) -> str:
        return textual_presenters.questions_markdown(snapshot)

    @staticmethod
    def _questions_select_markdown(snapshot: WorkflowNexusSnapshot) -> str:
        return textual_presenters.questions_select_markdown(snapshot)

    @staticmethod
    def _questions_rows(
        snapshot: WorkflowNexusSnapshot,
    ) -> tuple[tuple[str, str, str, str], ...]:
        return textual_presenters.questions_rows(snapshot)

    @staticmethod
    def _decisions_markdown(snapshot: WorkflowNexusSnapshot) -> str:
        return textual_presenters.decisions_markdown(snapshot)

    @staticmethod
    def _decisions_rows(
        snapshot: WorkflowNexusSnapshot,
    ) -> tuple[tuple[str, str], ...]:
        return textual_presenters.decisions_rows(snapshot)

    @staticmethod
    def _packages_markdown(snapshot: WorkflowNexusSnapshot) -> str:
        return textual_presenters.packages_markdown(snapshot)

    @staticmethod
    def _packages_rows(
        snapshot: WorkflowNexusSnapshot,
    ) -> tuple[tuple[str, str, str], ...]:
        return textual_presenters.packages_rows(snapshot)

    @staticmethod
    def _review_rows(
        snapshot: WorkflowNexusSnapshot,
    ) -> tuple[tuple[str, str], ...]:
        return textual_presenters.review_rows(snapshot)

    @staticmethod
    def _improve_rows(
        snapshot: WorkflowNexusSnapshot,
    ) -> tuple[tuple[str, str], ...]:
        return textual_presenters.improve_rows(snapshot)

    @staticmethod
    def _subtasks_markdown(snapshot: WorkflowNexusSnapshot) -> str:
        return textual_presenters.subtasks_markdown(snapshot)

    @staticmethod
    def _subtasks_rows(
        snapshot: WorkflowNexusSnapshot,
    ) -> tuple[tuple[str, str, str, str, str], ...]:
        return textual_presenters.subtasks_rows(snapshot)

    def _history_rows(
        self,
        snapshot: WorkflowNexusSnapshot,
    ) -> tuple[tuple[str, str], ...]:
        return textual_presenters.history_rows(snapshot, self._local_command_results)

    @staticmethod
    def _history_markdown(
        snapshot: WorkflowNexusSnapshot,
        rows: tuple[tuple[str, str], ...],
    ) -> str:
        return textual_presenters.history_markdown(snapshot, rows)

    def _handle_textual_context_command(self, command: str) -> None:
        """Show the current session context without reading stale shared.md state."""
        snapshot = self._fresh_textual_snapshot()
        body = self._snapshot_context_markdown(snapshot)
        if not self._snapshot_has_current_context(snapshot):
            if self.current_route == "start":
                self.notify(
                    NO_CURRENT_CONTEXT_MESSAGE,
                    title="Context",
                    severity="warning",
                )
                return
            self._record_slash_command_result(command, "Context", body)
            return

        result = self._local_command_snapshot(command, "Context", body)
        self._replace_local_command_result(result)
        snapshot = self._with_local_command_results(snapshot)
        self.active_snapshot = snapshot
        if self.current_route == "start":
            self.push_screen(ContextCommandModal(result))
            return
        self._apply_workflow_outcome(TextualWorkflowOutcome(snapshot))

    def _handle_textual_memory_command(self, args: list[str]) -> None:
        engine = engine_from_config(self.config)
        action = args[0].lower() if args else "stats"
        if action == "compact":
            body = compact_memory_markdown(
                engine,
                target_bytes=self.config.shared_compact_target_bytes,
                recent_records=self.config.memory_recent_records,
            )
            title = "Memory Compact"
            rows = memory_stats_rows(engine)
        elif action == "cleanup":
            apply, keep_latest, error = parse_oversized_cleanup_options(args[1:])
            if error:
                self._record_slash_command_result(
                    "/memory",
                    "Memory Cleanup",
                    error,
                    severity="warning",
                )
                return
            body = cleanup_oversized_backups_markdown(
                engine,
                apply=apply,
                keep_latest=keep_latest,
            )
            title = "Memory Cleanup"
            rows = ()
        else:
            body = memory_stats_markdown(engine)
            title = "Memory Stats"
            rows = memory_stats_rows(engine)
        self._record_slash_command_result(
            "/memory",
            title,
            body,
            table_columns=("Item", "Value"),
            table_rows=rows,
        )

    def _handle_textual_artifact_command(self, args: list[str]) -> None:
        record_id = args[0] if args else ""
        if not record_id:
            self._record_slash_command_result(
                "/artifact",
                "Artifact",
                "Usage: `/artifact <memory-id>`",
                severity="warning",
            )
            return
        body = artifact_markdown(engine_from_config(self.config), record_id)
        self._record_slash_command_result("/artifact", "Artifact", body)

    def _handle_textual_report_command(self, args: list[str]) -> None:
        snapshot = self._refresh_textual_snapshot()
        if args and args[0].lower() in {"save", "s"}:
            path = self._export_report_markdown(snapshot)
            if path is None:
                self._record_slash_command_result(
                    "/report",
                    "Report",
                    "No workflow data available to export.",
                    severity="warning",
                    empty=True,
                    action_hint="Start or resume a workflow before exporting a report.",
                )
                return
            self._record_slash_command_result(
                "/report",
                "Report",
                f"Report saved: `{path}`",
                result_kind="path",
                table_columns=("Item", "Value"),
                table_rows=(("Path", str(path)),),
            )
            return
        if not snapshot_has_report_data(snapshot):
            self._record_slash_command_result(
                "/report",
                "Report",
                "No workflow data available for a report.",
                severity="warning",
                empty=True,
                action_hint="Start or resume a workflow before opening a report.",
            )
            return
        self._record_slash_command_result(
            "/report",
            "Report",
            "Report screen opened.",
            table_columns=("Item", "Value"),
            table_rows=(
                ("Workflow", snapshot.session_id or "(new)"),
                ("State", snapshot.state or "idle"),
                ("Questions", str(len(snapshot.questions))),
                ("Decisions", str(len(snapshot.decisions))),
                (
                    "Work packages",
                    str(len(snapshot.central_work_packages) + len(snapshot.work_packages)),
                ),
                ("Subtasks", str(len(snapshot.subtasks))),
            ),
            start_modal=False,
        )
        self.switch_to("report")

    @staticmethod
    def _session_setting_body(message: str) -> str:
        return f"{message}\n\n{SESSION_ONLY_SETTING_NOTICE}"

    def _agent_rows(self) -> tuple[tuple[str, str, str], ...]:
        return tuple(
            (
                name,
                "yes" if spec.enabled else "no",
                spec.provider.value if hasattr(spec.provider, "value") else str(spec.provider),
            )
            for name, spec in sorted(self.config.agents.items())
        )

    def _handle_textual_rounds_command(
        self,
        command_name: str,
        args: list[str],
    ) -> None:
        if not args:
            self._record_slash_command_result(
                command_name,
                "Rounds",
                self._session_setting_body(
                    f"Current max rounds: `{self.config.max_deliberation_rounds}`."
                ),
                table_columns=("Item", "Value"),
                table_rows=(
                    ("Current max rounds", str(self.config.max_deliberation_rounds)),
                    ("Allowed range", "1..20"),
                ),
                action_hint="Use `/rounds <1..20>` to change it for this session.",
            )
            return
        try:
            rounds = int(args[0])
        except ValueError:
            self._record_slash_command_result(
                command_name,
                "Rounds",
                "Invalid number.",
                severity="warning",
                action_hint="Use `/rounds <1..20>`.",
            )
            return
        if rounds < 1 or rounds > 20:
            self._record_slash_command_result(
                command_name,
                "Rounds",
                "Rounds must be between 1 and 20.",
                severity="warning",
                action_hint="Use `/rounds <1..20>`.",
            )
            return
        self.config.max_deliberation_rounds = rounds
        self._record_slash_command_result(
            command_name,
            "Rounds",
            self._session_setting_body(f"Max rounds set to `{rounds}` for this session only."),
            table_columns=("Item", "Value"),
            table_rows=(
                ("Current max rounds", str(self.config.max_deliberation_rounds)),
                ("Allowed range", "1..20"),
            ),
        )

    def _handle_textual_agent_command(
        self,
        command_name: str,
        args: list[str],
    ) -> None:
        if not args:
            self._record_slash_command_result(
                command_name,
                "Agent",
                self._session_setting_body("Current agent session settings."),
                table_columns=("Agent", "Enabled", "Provider"),
                table_rows=self._agent_rows(),
                action_hint="Use `/agent <name> on|off` to change one agent.",
            )
            return
        if len(args) < 2:
            self._record_slash_command_result(
                command_name,
                "Agent",
                "Usage: `/agent <name> on|off`",
                severity="warning",
                table_columns=("Agent", "Enabled", "Provider"),
                table_rows=self._agent_rows(),
            )
            return
        name, action = args[0].lower(), args[1].lower()
        spec = self.config.agents.get(name)
        if spec is None:
            self._record_slash_command_result(
                command_name,
                "Agent",
                f"Unknown agent: `{name}`",
                severity="warning",
                table_columns=("Agent", "Enabled", "Provider"),
                table_rows=self._agent_rows(),
            )
            return
        if action not in {"on", "off"}:
            self._record_slash_command_result(
                command_name,
                "Agent",
                "Usage: `/agent <name> on|off`",
                severity="warning",
                table_columns=("Agent", "Enabled", "Provider"),
                table_rows=self._agent_rows(),
            )
            return
        spec.enabled = action == "on"
        status = "enabled" if spec.enabled else "disabled"
        self._record_slash_command_result(
            command_name,
            "Agent",
            self._session_setting_body(f"Agent `{name}` {status} for this session only."),
            table_columns=("Agent", "Enabled", "Provider"),
            table_rows=self._agent_rows(),
        )

    def _handle_textual_caveman_command(
        self,
        command_name: str,
        args: list[str],
    ) -> None:
        if not args:
            mode = "on" if self.config.caveman_mode else "off"
            self._record_slash_command_result(
                command_name,
                "Caveman",
                self._session_setting_body(
                    f"Caveman: `{mode}` (`{self.config.caveman_intensity}`)."
                ),
                table_columns=("Item", "Value"),
                table_rows=(
                    ("Mode", mode),
                    ("Intensity", self.config.caveman_intensity),
                    ("Allowed", "on, off, lite, full, ultra"),
                ),
                action_hint="Use `/caveman <mode>` to change it for this session.",
            )
            return
        action = args[0].lower()
        if action in {"off", "disable"}:
            self.config.caveman_mode = False
        elif action in {"on", "enable"}:
            self.config.caveman_mode = True
        elif action in VALID_CAVEMAN_INTENSITIES:
            self.config.caveman_mode = True
            self.config.caveman_intensity = action
        else:
            self._record_slash_command_result(
                command_name,
                "Caveman",
                "Use: /caveman [on|off|lite|full|ultra]",
                severity="warning",
                action_hint="Allowed modes: on, off, lite, full, ultra.",
            )
            return
        mode = "on" if self.config.caveman_mode else "off"
        self._record_slash_command_result(
            command_name,
            "Caveman",
            self._session_setting_body(
                f"Caveman set to `{mode}` (`{self.config.caveman_intensity}`) "
                "for this session only."
            ),
            table_columns=("Item", "Value"),
            table_rows=(
                ("Mode", mode),
                ("Intensity", self.config.caveman_intensity),
                ("Allowed", "on, off, lite, full, ultra"),
            ),
        )

    def _handle_textual_target_command(self, args: list[str]) -> None:
        if not args:
            target = getattr(self.workflow_controller, "workflow", None)
            current = None
            if target is not None:
                current = target.session.target_workspace
            self._record_slash_command_result(
                "/target",
                "Target",
                f"Current target: `{current or '(not set)'}`",
                empty=current is None,
                action_hint=(
                    "Use `/target <path>` or Select Workspace before execution."
                ),
            )
            return
        action = args[0].lower()
        if action in {"clear", "reset", "none"}:
            outcome = self.workflow_controller.clear_target_workspace()
            self.confirmed_preflight = None
            self._apply_workflow_outcome(outcome)
            self._record_slash_command_result(
                "/target",
                "Target",
                "Target workspace cleared.",
            )
            return
        path = self._resolve_target_path(" ".join(args))
        if self._is_control_repo_target(path):
            self.push_screen(
                TargetWorkspaceConfirmModal(
                    target_path=path,
                    control_repo=self.config.project_dir,
                ),
                lambda confirmed: self._on_target_workspace_confirmed(
                    path,
                    confirmed,
                ),
            )
            return
        self._set_textual_target_workspace(path, control_repo_confirmed=False)

    def _on_target_workspace_confirmed(
        self,
        path: Path,
        confirmed: bool | None,
    ) -> None:
        if confirmed:
            self._set_textual_target_workspace(path, control_repo_confirmed=True)
            return
        self._record_slash_command_result(
            "/target",
            "Target",
            "Target workspace selection cancelled.",
            severity="warning",
            empty=True,
            action_hint="Choose a workspace outside the Trinity control repo.",
        )

    def _set_textual_target_workspace(
        self,
        path: Path,
        *,
        control_repo_confirmed: bool,
    ) -> None:
        try:
            if path.exists() and not path.is_dir():
                self._record_slash_command_result(
                    "/target",
                    "Target",
                    f"Target path exists but is not a directory: `{path}`",
                    severity="warning",
                    empty=True,
                )
                return
            path.mkdir(parents=True, exist_ok=True)
            resolved = path.resolve()
        except OSError as exc:
            self._record_slash_command_result(
                "/target",
                "Target",
                f"Could not prepare target workspace: {exc}",
                severity="warning",
                empty=True,
            )
            return

        outcome = self.workflow_controller.set_target_workspace(
            resolved,
            control_repo_confirmed=control_repo_confirmed,
        )
        if isinstance(outcome, TextualWorkflowOutcome):
            self._remember_confirmed_target_preflight(resolved, outcome.snapshot)
            self._apply_workflow_outcome(outcome)
        else:
            self._remember_confirmed_target_preflight(
                resolved,
                self.active_snapshot
                or self.workflow_controller.snapshot()
                or self.snapshot_adapter.load_snapshot(),
            )
        self.workspace_candidate = resolved
        self._sync_nexus_workspace_candidate()
        self._record_slash_command_result(
            "/target",
            "Target",
            f"Target workspace: `{resolved}`",
            table_columns=("Item", "Value"),
            table_rows=(
                ("Path", str(resolved)),
                (
                    "Inside control repo",
                    "yes" if self._is_control_repo_target(resolved) else "no",
                ),
                (
                    "Control repo confirmed",
                    "yes" if control_repo_confirmed else "no",
                ),
            ),
        )

    def _sync_nexus_workspace_candidate(self) -> None:
        if not self._screens_installed:
            return
        self.get_screen("nexus", NexusScreen).set_workspace_candidate(
            self.workspace_candidate,
        )

    def _resolve_target_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self.config.project_dir / path
        return path

    def _is_control_repo_target(self, path: Path) -> bool:
        target = self._absolute_path(path)
        control_repo = self._absolute_path(self.config.project_dir)
        return target == control_repo or control_repo in target.parents

    @staticmethod
    def _absolute_path(path: Path) -> Path:
        try:
            return path.expanduser().resolve(strict=False)
        except OSError:
            return path.expanduser().absolute()

    def _handle_textual_resume_command(self, args: list[str]) -> None:
        if not args:
            archives = self.workflow_controller.list_resume_options()
            if not archives:
                self._record_slash_command_result(
                    "/resume",
                    "Resume",
                    "No saved workflow sessions to resume.",
                    empty=True,
                    action_hint="Start and archive a workflow before using `/resume`.",
                )
                return
            self._record_slash_command_result(
                "/resume",
                "Resume",
                self._resume_archives_markdown(archives),
                table_columns=("Selector", "Workflow", "State", "Goal"),
                table_rows=self._resume_archive_rows(archives),
                action_hint="Pick a workflow from the resume modal.",
                start_modal=False,
            )
            self.push_screen(
                ResumeWorkflowPicker(archives, lang=self.config.lang),
                self._on_resume_archive_selected,
            )
            return
        selector = args[0].lower()
        self._resume_textual_workflow(selector)

    def _on_resume_archive_selected(self, selector: str | None) -> None:
        if selector is None:
            self._record_slash_command_result(
                "/resume",
                "Resume",
                "Resume selection cancelled.",
                empty=True,
                action_hint="Run `/resume` again to choose an archived workflow.",
            )
            return
        self._resume_textual_workflow(selector)

    def _resume_textual_workflow(self, selector: str) -> None:
        outcome = self.workflow_controller.resume_workflow(selector)
        message = outcome.message
        if outcome.message:
            outcome = replace(outcome, message="")
        self._apply_workflow_outcome(outcome)
        failed = bool(message and message.startswith("No "))
        if message:
            self._record_slash_command_result(
                "/resume",
                "Resume",
                message,
                severity="warning" if failed else "info",
                empty=failed,
                table_columns=("Item", "Value"),
                table_rows=self._resume_result_rows(outcome.snapshot),
                start_modal=failed,
            )
        if not failed:
            self.switch_to("nexus")
            if outcome.execution_recovery_required:
                self._present_execution_recovery(
                    "/resume",
                    outcome.snapshot,
                    "Previous execution was interrupted before Trinity could collect all results.",
                )
            self._handle_textual_context_command("/context")

    @staticmethod
    def _resume_archives_markdown(
        archives: list[object],
    ) -> str:
        return textual_presenters.resume_archives_markdown(archives)

    @staticmethod
    def _resume_archive_rows(
        archives: list[object],
    ) -> tuple[tuple[str, str, str, str], ...]:
        return textual_presenters.resume_archive_rows(archives)

    @staticmethod
    def _resume_result_rows(
        snapshot: WorkflowNexusSnapshot,
    ) -> tuple[tuple[str, str], ...]:
        return textual_presenters.resume_result_rows(snapshot)

    def _handle_textual_answer_command(self, args: list[str]) -> None:
        if not args:
            self._record_slash_command_result(
                "/answer",
                "Answer",
                "Usage: /answer <question-id|index|next> <answer>",
                severity="warning",
                empty=True,
                action_hint="Run `/questions` to inspect pending questions first.",
            )
            return
        replace = False
        filtered: list[str] = []
        for arg in args:
            if arg in {"--replace", "-r"}:
                replace = True
            else:
                filtered.append(arg)
        if not filtered:
            self._record_slash_command_result(
                "/answer",
                "Answer",
                "Usage: /answer <question-id|index|next> <answer>",
                severity="warning",
                empty=True,
                action_hint="Run `/questions` to inspect pending questions first.",
            )
            return
        if len(filtered) == 1 and filtered[0].isdigit():
            outcome = self.workflow_controller.answer_question_option(
                filtered[0],
                replace=replace,
            )
        elif len(filtered) == 1:
            outcome = self.workflow_controller.answer_question(
                "next",
                filtered[0],
                replace=replace,
            )
        else:
            outcome = self.workflow_controller.answer_question(
                filtered[0],
                " ".join(filtered[1:]),
                replace=replace,
            )
        message = outcome.message
        if message:
            outcome = replace(outcome, message="")
        self._apply_workflow_outcome(outcome)
        if message:
            self._record_slash_command_result(
                "/answer",
                "Answer",
                message,
                severity="warning" if message.startswith("No ") else "info",
                empty=message.startswith("No "),
            )

    def _handle_textual_execute_retry_command(self, args: list[str]) -> None:
        selector, package_ids = self._parse_execute_retry_args(args)
        self.workflow_controller.preview_execution_retry(selector, package_ids)
        snapshot = self._refresh_textual_snapshot()
        if not snapshot.work_package_details:
            self._record_slash_command_result(
                "/execute-retry",
                "Execute Retry",
                "No work packages are available in the current workflow.",
                severity="warning",
                empty=True,
                action_hint="Finish planning and execute at least one package first.",
            )
            return
        self.push_screen(
            ExecutionRetryModal(
                snapshot,
                selector=selector,
                package_ids=tuple(package_ids),
                lang=self.config.lang,
            ),
            self._on_execute_retry_selected,
        )

    @staticmethod
    def _parse_execute_retry_args(args: list[str]) -> tuple[str, list[str]]:
        if not args:
            return "all", []
        first = args[0].lower()
        if first in {"all", "failed", "blocked", "interrupted", "custom"}:
            return first, args[1:]
        return "custom", args

    def _on_execute_retry_selected(
        self,
        selection: ExecutionRetrySelection | None,
    ) -> None:
        if selection is None:
            return
        outcome = self.workflow_controller.confirm_execution_retry(
            selection.selector,
            list(selection.package_ids),
        )
        if outcome.target_workspace_required:
            self._pending_execute_retry = selection
            self._apply_workflow_outcome(outcome)
            self._open_execute_workspace_picker(outcome.snapshot)
            return
        self._apply_workflow_outcome(outcome)
        if outcome.execution_requested:
            execution = self.get_screen("execution", ExecutionMatrixScreen)
            execution.apply_execution_state(self.confirmed_preflight, outcome.snapshot)
            self.switch_to("execution")

    def _advance_activity_frame(self) -> None:
        if self.current_route == "nexus" and self._screens_installed:
            nexus = self.get_screen("nexus", NexusScreen)
            nexus.advance_activity_frame()

    def switch_to(self, route: WorkbenchRoute) -> None:
        if route == "report" and self._screens_installed:
            report = self.get_screen("report", ReportScreen)
            report.apply_snapshot(self.active_snapshot or self.snapshot_adapter.load_snapshot())
            # Build a structured DeliberationReport for richer rendering
            try:
                from trinity.tui.report import DeliberationReportBuilder
                from trinity.workflow import WorkflowPersistence

                persistence = WorkflowPersistence(self.config.effective_state_dir)
                session = persistence.load()
                if session and session.goal:
                    events = persistence.load_events_for_workflow(
                        session.id,
                        tail=WORKFLOW_EVENT_DISPLAY_LIMIT,
                    )
                    structured = DeliberationReportBuilder(
                        session,
                        result=None,
                        events=events,
                        snapshot=self.active_snapshot,
                    ).build()
                    report.apply_report(structured)
            except Exception:
                pass  # Fallback to snapshot rendering
        if route == "execution" and self._screens_installed:
            execution = self.get_screen("execution", ExecutionMatrixScreen)
            execution.apply_execution_state(
                self.confirmed_preflight,
                self.active_snapshot
                or self.workflow_controller.snapshot()
                or self.snapshot_adapter.load_snapshot(),
            )
        self.current_route = route
        self.switch_screen(route)
        if route == "nexus" or self.active_snapshot is not None:
            self.call_after_refresh(self._refresh_current_route_from_active_snapshot)

    def action_go_start(self) -> None:
        self.active_snapshot = None
        self.initial_prompt = None
        outcome = self.workflow_controller.new_session()
        self.active_snapshot = outcome.snapshot
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
        snapshot = event.snapshot or self.active_snapshot or self.snapshot_adapter.load_snapshot()
        self._export_report_markdown(snapshot)

    def _export_report_markdown(self, snapshot: WorkflowNexusSnapshot) -> Path | None:
        """Save a report as Markdown using the shared DeliberationReport builder."""
        from trinity.tui.report import DeliberationReportBuilder
        from trinity.workflow import WorkflowPersistence

        report_dir = self.config.effective_state_dir / "reports"

        # Build from the full WorkflowSession for richer output
        persistence = WorkflowPersistence(self.config.effective_state_dir)
        session = persistence.load()
        if session is not None:
            filepath = unique_report_path(report_dir, session.id)
            events = persistence.load_events_for_workflow(session.id)
            builder = DeliberationReportBuilder(
                session,
                result=None,
                events=events,
                snapshot=snapshot,
            )
            report = builder.build()
            markdown = report.to_markdown()
        elif snapshot_has_report_data(snapshot):
            filepath = unique_report_path(report_dir, snapshot.session_id)
            markdown = snapshot_report_markdown(snapshot)
        else:
            self.notify(
                "No workflow data available to export.",
                title="Export Unavailable",
                severity="warning",
            )
            return None

        filepath.write_text(markdown, encoding="utf-8")
        if self._screens_installed:
            self.get_screen("report", ReportScreen).show_export_path(filepath)
        self.notify(f"Report saved: {filepath}", title="Export Complete")
        return filepath


def run_textual_app(config: TrinityConfig) -> None:
    """Run the Textual workbench."""
    TrinityTextualApp(config).run()
