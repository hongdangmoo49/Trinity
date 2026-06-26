"""Textual application shell for Trinity."""

from __future__ import annotations

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
from trinity.providers.model_discovery import (
    ProviderModelChoice,
    discover_provider_models,
)
from trinity.slash_commands import parse_execute_retry_args, parse_slash_command
from trinity.textual_app.command_parsers import (
    parse_agent_args,
    parse_answer_args,
    parse_ask_args,
    parse_caveman_args,
    parse_rounds_args,
)
from trinity.textual_app import presenters as textual_presenters
from trinity.textual_app.local_commands import (
    append_local_command_event,
    replace_local_command_result,
    snapshot_with_local_command_results,
)
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
        ("ctrl+4", "go_report"): ("binding_report", None),
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

    .execution-lane-header {
        height: 1;
        width: 100%;
        color: $accent;
        text-style: bold;
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
        width: 18;
        color: $text-muted;
    }

    .execution-package-actions {
        width: 16;
        height: 1;
    }

    .execution-package-spec {
        width: 8;
    }

    .execution-package-retry {
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
        self.install_screen(ExecutionMatrixScreen(lang=self.config.lang), "execution")
        self.install_screen(ReportScreen(lang=self.config.lang), "report")

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
        changed_choices: dict[str, tuple[ProviderModelChoice, ...]] = {}
        for name, choices in choices_by_agent.items():
            next_choices = tuple(choices)
            if self._agent_model_choices.get(name, ()) == next_choices:
                continue
            self._agent_model_choices[name] = next_choices
            changed_choices[name] = next_choices
        if not changed_choices:
            return
        for screen_name, screen_type in (
            ("start", StartScreen),
            ("nexus", NexusScreen),
        ):
            screen = self.get_screen(screen_name, screen_type)
            screen.set_agent_model_choices(changed_choices)
        if isinstance(self.screen, ModelSettingsModal):
            self.screen.set_model_choices(changed_choices)

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
        selector = event.selector
        package_ids = list(event.package_ids)
        self.workflow_controller.preview_execution_retry(selector, package_ids)
        snapshot = self.workflow_controller.snapshot() or event.snapshot
        self._apply_workflow_outcome(TextualWorkflowOutcome(snapshot))
        if not snapshot.work_package_details:
            self.notify(
                textual_presenters.execute_retry_no_packages_markdown(
                    lang=self.config.lang
                ),
                title=textual_presenters.execute_retry_title(lang=self.config.lang),
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

    def on_execution_matrix_screen_review_requested(
        self,
        event: ExecutionMatrixScreen.ReviewRequested,
    ) -> None:
        event.stop()
        args = ("wp", *event.package_ids)
        outcome = self.workflow_controller.request_review(args)
        message = outcome.message
        if message:
            outcome = replace(outcome, message="")
        self._apply_workflow_outcome(outcome)
        if message:
            self.notify(
                textual_presenters.workflow_outcome_message_markdown(
                    message,
                    lang=self.config.lang,
                ),
                severity=(
                    "warning"
                    if message.startswith("No pending")
                    or "target workspace" in message.lower()
                    or "still running" in message.lower()
                    else "info"
                ),
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
        package_ids = textual_presenters.review_repair_blocked_ids(current)
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
                    lang=self.config.lang,
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
            textual_presenters.target_title(lang=self.config.lang),
            textual_presenters.target_selection_cancelled_markdown(lang=self.config.lang),
            severity="warning",
            empty=True,
            action_hint=textual_presenters.target_control_repo_action_hint(
                lang=self.config.lang
            ),
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
                    lang=self.config.lang,
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
            textual_presenters.target_title(lang=self.config.lang),
            textual_presenters.target_preflight_cancelled_markdown(lang=self.config.lang),
            severity="warning",
            empty=True,
            action_hint=textual_presenters.target_control_repo_action_hint(
                lang=self.config.lang
            ),
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
        snapshot = snapshot_with_local_command_results(
            outcome.snapshot,
            self._local_command_results,
        )
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
            self.notify(
                textual_presenters.workflow_outcome_message_markdown(
                    outcome.message,
                    lang=self.config.lang,
                )
            )
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
                textual_presenters.syntax_error_title(lang=self.config.lang),
                parsed.error,
                severity="warning",
            )
            return
        if not parsed.token:
            return
        if parsed.spec is None:
            suggestions = textual_presenters.slash_command_suggestions(parsed.token)
            self._record_slash_command_result(
                parsed.token,
                textual_presenters.unknown_command_title(lang=self.config.lang),
                textual_presenters.unknown_command_markdown(
                    parsed.token,
                    suggestions,
                    lang=self.config.lang,
                ),
                severity="warning",
                table_columns=textual_presenters.unknown_command_table_columns(
                    lang=self.config.lang
                ),
                table_rows=textual_presenters.unknown_command_rows(
                    suggestions,
                    lang=self.config.lang,
                ),
            )
            return

        command = parsed.command_id
        args = list(parsed.args)

        if command in {"quit", "exit", "q"}:
            self.push_screen(
                ConfirmQuitModal(
                    running=bool(getattr(self.workflow_controller, "is_running", False)),
                    lang=self.config.lang,
                ),
                self._on_quit_confirmed,
            )
            return
        if command == "help":
            self._record_slash_command_result(
                parsed.spec.name,
                textual_presenters.help_title(lang=self.config.lang),
                textual_presenters.help_markdown(lang=self.config.lang),
                table_columns=textual_presenters.help_table_columns(
                    lang=self.config.lang
                ),
                table_rows=textual_presenters.help_rows(lang=self.config.lang),
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
                textual_presenters.workflow_title(lang=self.config.lang),
                textual_presenters.snapshot_workflow_markdown(
                    snapshot,
                    lang=self.config.lang,
                ),
                table_columns=textual_presenters.status_table_columns(lang=self.config.lang),
                table_rows=textual_presenters.snapshot_workflow_rows(
                    snapshot,
                    lang=self.config.lang,
                ),
            )
            return
        if command == "questions":
            snapshot = self._refresh_textual_snapshot()
            select_requested = any(arg.lower() in {"--select", "-s"} for arg in args)
            has_questions = bool(snapshot.questions)
            self._record_slash_command_result(
                parsed.spec.name,
                textual_presenters.questions_title(lang=self.config.lang),
                textual_presenters.questions_select_markdown(
                    snapshot,
                    lang=self.config.lang,
                )
                if select_requested
                else textual_presenters.questions_markdown(
                    snapshot,
                    lang=self.config.lang,
                ),
                empty=not has_questions,
                action_hint=textual_presenters.questions_action_hint(
                    has_questions=has_questions,
                    lang=self.config.lang,
                ),
                table_columns=textual_presenters.questions_table_columns(
                    lang=self.config.lang
                ),
                table_rows=textual_presenters.questions_rows(
                    snapshot,
                    lang=self.config.lang,
                ),
            )
            return
        if command == "decisions":
            snapshot = self._refresh_textual_snapshot()
            has_decisions = bool(snapshot.decisions)
            self._record_slash_command_result(
                parsed.spec.name,
                textual_presenters.decisions_title(lang=self.config.lang),
                textual_presenters.decisions_markdown(
                    snapshot,
                    lang=self.config.lang,
                ),
                empty=not has_decisions,
                action_hint=textual_presenters.decisions_action_hint(
                    has_decisions=has_decisions,
                    lang=self.config.lang,
                ),
                table_columns=textual_presenters.decisions_table_columns(
                    lang=self.config.lang
                ),
                table_rows=textual_presenters.decisions_rows(
                    snapshot,
                    lang=self.config.lang,
                ),
            )
            return
        if command == "packages":
            snapshot = self._refresh_textual_snapshot()
            has_packages = bool(snapshot.work_packages or snapshot.central_work_packages)
            self._record_slash_command_result(
                parsed.spec.name,
                textual_presenters.packages_title(lang=self.config.lang),
                textual_presenters.packages_markdown(
                    snapshot,
                    lang=self.config.lang,
                ),
                empty=not has_packages,
                action_hint=textual_presenters.packages_action_hint(
                    has_packages=has_packages,
                    lang=self.config.lang,
                ),
                table_columns=textual_presenters.packages_table_columns(
                    lang=self.config.lang
                ),
                table_rows=textual_presenters.packages_rows(
                    snapshot,
                    lang=self.config.lang,
                ),
            )
            return
        if command == "subtasks":
            snapshot = self._refresh_textual_snapshot()
            has_subtasks = bool(snapshot.subtasks)
            self._record_slash_command_result(
                parsed.spec.name,
                textual_presenters.subtasks_title(lang=self.config.lang),
                textual_presenters.subtasks_markdown(
                    snapshot,
                    lang=self.config.lang,
                ),
                empty=not has_subtasks,
                action_hint=textual_presenters.subtasks_action_hint(
                    has_subtasks=has_subtasks,
                    lang=self.config.lang,
                ),
                table_columns=textual_presenters.subtasks_table_columns(
                    lang=self.config.lang
                ),
                table_rows=textual_presenters.subtasks_rows(
                    snapshot,
                    lang=self.config.lang,
                ),
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
            history_rows = textual_presenters.history_rows(
                snapshot,
                self._local_command_results,
                lang=self.config.lang,
            )
            self._record_slash_command_result(
                parsed.spec.name,
                textual_presenters.history_title(lang=self.config.lang),
                textual_presenters.history_markdown(
                    snapshot,
                    history_rows,
                    lang=self.config.lang,
                ),
                empty=not history_rows,
                action_hint=textual_presenters.history_action_hint(
                    has_history=bool(history_rows),
                    lang=self.config.lang,
                ),
                table_columns=textual_presenters.history_table_columns(
                    lang=self.config.lang
                ),
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
                textual_presenters.save_title(lang=self.config.lang),
                textual_presenters.save_auto_persist_markdown(lang=self.config.lang),
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
                    textual_presenters.review_title(lang=self.config.lang),
                    textual_presenters.workflow_outcome_message_markdown(
                        message,
                        lang=self.config.lang,
                    ),
                    severity=(
                        "warning"
                        if message.startswith("No review") or "not connected" in message
                        else "info"
                    ),
                    table_columns=textual_presenters.review_table_columns(
                        lang=self.config.lang
                    ),
                    table_rows=textual_presenters.review_rows(
                        outcome.snapshot,
                        lang=self.config.lang,
                    ),
                    action_hint=textual_presenters.review_action_hint(
                        lang=self.config.lang
                    ),
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
                    textual_presenters.improve_title(lang=self.config.lang),
                    textual_presenters.workflow_outcome_message_markdown(
                        message,
                        lang=self.config.lang,
                    ),
                    severity=(
                        "warning"
                        if message.startswith("No matching")
                        or "required" in message
                        else "info"
                    ),
                    table_columns=textual_presenters.improve_table_columns(
                        lang=self.config.lang
                    ),
                    table_rows=textual_presenters.improve_rows(
                        outcome.snapshot,
                        lang=self.config.lang,
                    ),
                    action_hint=textual_presenters.improve_action_hint(
                        lang=self.config.lang
                    ),
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
                    textual_presenters.execute_title(lang=self.config.lang),
                    textual_presenters.workflow_outcome_message_markdown(
                        message,
                        lang=self.config.lang,
                    ),
                    severity="warning",
                    empty=True,
                    action_hint=textual_presenters.execute_finish_planning_action_hint(
                        lang=self.config.lang
                    ),
                )
            if outcome.target_workspace_required:
                self._open_execute_workspace_picker(outcome.snapshot)
            return

    def _handle_textual_ask_command(self, command_name: str, args: list[str]) -> None:
        parsed = parse_ask_args(
            args,
            self.config.active_agents.keys(),
            lang=self.config.lang,
        )
        if parsed.error:
            self._record_slash_command_result(
                command_name,
                textual_presenters.ask_title(lang=self.config.lang),
                parsed.error,
                severity="warning",
                empty=True,
                action_hint=textual_presenters.ask_action_hint(lang=self.config.lang),
            )
            return

        if self.current_route == "start":
            self.initial_prompt = parsed.prompt
            nexus = self.get_screen("nexus", NexusScreen)
            nexus.set_initial_prompt(parsed.prompt)
            nexus.set_agent_selection(
                parsed.target_agents,
                parsed.agent_model_overrides,
            )
            target_workspace = self._safe_start_target_workspace(self.workspace_candidate)
            outcome = self.workflow_controller.start_prompt(
                parsed.prompt,
                target_workspace=target_workspace,
                target_agents=parsed.target_agents,
                agent_model_overrides=parsed.agent_model_overrides,
            )
            self._remember_confirmed_target_preflight(target_workspace, outcome.snapshot)
            self._apply_workflow_outcome(outcome)
            self.switch_to("nexus")
            return

        nexus = self.get_screen("nexus", NexusScreen)
        nexus.set_agent_selection(
            parsed.target_agents,
            parsed.agent_model_overrides,
        )
        outcome = self.workflow_controller.submit_follow_up(
            parsed.prompt,
            target_agents=parsed.target_agents,
            agent_model_overrides=parsed.agent_model_overrides,
        )
        self._apply_workflow_outcome(outcome)
        if outcome.target_workspace_required:
            self._open_execute_workspace_picker(outcome.snapshot)

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
        result = textual_presenters.local_command_snapshot(
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
        append_local_command_event(self.config.effective_state_dir, result)
        self._present_local_command_result(
            result,
            start_modal=start_modal,
            notify=True,
        )

    def _present_local_command_result(
        self,
        result: LocalCommandSnapshot,
        *,
        start_modal: bool = True,
        notify: bool = True,
    ) -> None:
        """Render a local slash command result on the active Textual surface."""
        self._local_command_results = replace_local_command_result(
            self._local_command_results,
            result,
        )
        snapshot = snapshot_with_local_command_results(
            self._current_textual_snapshot(),
            self._local_command_results,
        )
        self.active_snapshot = snapshot
        if self.current_route == "start" and start_modal:
            self.push_screen(LocalCommandModal(result, lang=self.config.lang))
        else:
            self._apply_workflow_outcome(TextualWorkflowOutcome(snapshot))
        if notify and self.current_route != "start":
            notify_severity = (
                "warning" if result.severity in {"warning", "error"} else "information"
            )
            self.notify(
                result.title,
                title=textual_presenters.slash_command_notification_title(
                    lang=self.config.lang
                ),
                severity=notify_severity,
            )

    def _show_textual_status(
        self,
        command: str,
        snapshot: WorkflowNexusSnapshot,
    ) -> None:
        """Show status in the surface appropriate for the current Textual route."""
        result = textual_presenters.local_command_snapshot(
            command,
            textual_presenters.status_title(lang=self.config.lang),
            textual_presenters.snapshot_status_markdown(
                snapshot,
                lang=self.config.lang,
            ),
            table_columns=textual_presenters.status_table_columns(lang=self.config.lang),
            table_rows=textual_presenters.snapshot_status_rows(
                snapshot,
                lang=self.config.lang,
            ),
        )
        self._local_command_results = replace_local_command_result(
            self._local_command_results,
            result,
        )
        snapshot = snapshot_with_local_command_results(
            snapshot,
            self._local_command_results,
        )
        self.active_snapshot = snapshot
        if self.current_route == "start":
            self.push_screen(StatusCommandModal(result, lang=self.config.lang))
            return
        self._apply_workflow_outcome(TextualWorkflowOutcome(snapshot))

    def _open_model_settings_modal(self) -> None:
        """Open the model settings modal for the active prompt selector."""
        selector = self._active_agent_selector()
        if selector is None:
            self.notify(
                textual_presenters.model_settings_unavailable_markdown(
                    lang=self.config.lang
                ),
                title=textual_presenters.model_settings_title(lang=self.config.lang),
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
            textual_presenters.model_settings_updated_markdown(lang=self.config.lang),
            title=textual_presenters.model_settings_title(lang=self.config.lang),
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
        localized_message = textual_presenters.workflow_outcome_message_markdown(
            message,
            lang=self.config.lang,
        ).strip()
        body_parts = [localized_message] if localized_message else []
        body_parts.append(
            textual_presenters.execution_recovery_markdown(
                snapshot,
                lang=self.config.lang,
            )
        )
        self._record_slash_command_result(
            command,
            textual_presenters.execution_recovery_title(lang=self.config.lang),
            "\n\n".join(body_parts),
            severity="warning",
            action_hint=textual_presenters.execution_recovery_action_hint(
                lang=self.config.lang
            ),
            table_columns=textual_presenters.execution_recovery_table_columns(
                lang=self.config.lang
            ),
            table_rows=textual_presenters.execution_recovery_rows(
                snapshot,
                lang=self.config.lang,
            ),
            start_modal=False,
        )

    def _present_review_repair_details(self, snapshot: WorkflowNexusSnapshot) -> None:
        lang = self.config.lang
        self._record_slash_command_result(
            "/review",
            textual_presenters.review_repair_title(lang=lang),
            textual_presenters.review_repair_details_markdown(snapshot, lang=lang),
            severity="warning",
            action_hint=textual_presenters.review_repair_action_hint(lang=lang),
            table_columns=textual_presenters.review_repair_table_columns(lang=lang),
            table_rows=textual_presenters.review_repair_rows(snapshot, lang=lang),
            start_modal=False,
        )

    def _handle_textual_context_command(self, command: str) -> None:
        """Show the current session context without reading stale shared.md state."""
        snapshot = self._fresh_textual_snapshot()
        body = textual_presenters.snapshot_context_markdown(
            snapshot,
            lang=self.config.lang,
        )
        if not textual_presenters.snapshot_has_current_context(snapshot):
            if self.current_route == "start":
                self.notify(
                    textual_presenters.context_no_current_markdown(
                        lang=self.config.lang
                    ),
                    title=textual_presenters.context_title(lang=self.config.lang),
                    severity="warning",
                )
                return
            self._record_slash_command_result(
                command,
                textual_presenters.context_title(lang=self.config.lang),
                body,
            )
            return

        result = textual_presenters.local_command_snapshot(
            command,
            textual_presenters.context_title(lang=self.config.lang),
            body,
        )
        self._local_command_results = replace_local_command_result(
            self._local_command_results,
            result,
        )
        snapshot = snapshot_with_local_command_results(
            snapshot,
            self._local_command_results,
        )
        self.active_snapshot = snapshot
        if self.current_route == "start":
            self.push_screen(ContextCommandModal(result, lang=self.config.lang))
            return
        self._apply_workflow_outcome(TextualWorkflowOutcome(snapshot))

    def _handle_textual_memory_command(self, args: list[str]) -> None:
        engine = engine_from_config(self.config)
        action = args[0].lower() if args else "stats"
        lang = self.config.lang
        if action == "compact":
            body = compact_memory_markdown(
                engine,
                target_bytes=self.config.shared_compact_target_bytes,
                recent_records=self.config.memory_recent_records,
            )
            title = textual_presenters.memory_title("compact", lang=lang)
            rows = memory_stats_rows(engine)
        elif action == "cleanup":
            apply, keep_latest, error = parse_oversized_cleanup_options(args[1:])
            if error:
                self._record_slash_command_result(
                    "/memory",
                    textual_presenters.memory_title("cleanup", lang=lang),
                    textual_presenters.memory_cleanup_error_markdown(error, lang=lang),
                    severity="warning",
                )
                return
            body = cleanup_oversized_backups_markdown(
                engine,
                apply=apply,
                keep_latest=keep_latest,
            )
            title = textual_presenters.memory_title("cleanup", lang=lang)
            rows = ()
        else:
            body = memory_stats_markdown(engine)
            title = textual_presenters.memory_title("stats", lang=lang)
            rows = memory_stats_rows(engine)
        self._record_slash_command_result(
            "/memory",
            title,
            body,
            table_columns=textual_presenters.status_table_columns(lang=lang),
            table_rows=rows,
        )

    def _handle_textual_artifact_command(self, args: list[str]) -> None:
        lang = self.config.lang
        record_id = args[0] if args else ""
        if not record_id:
            self._record_slash_command_result(
                "/artifact",
                textual_presenters.artifact_title(lang=lang),
                textual_presenters.artifact_usage_markdown(lang=lang),
                severity="warning",
            )
            return
        body = artifact_markdown(engine_from_config(self.config), record_id, lang=lang)
        self._record_slash_command_result(
            "/artifact",
            textual_presenters.artifact_title(lang=lang),
            body,
        )

    def _handle_textual_report_command(self, args: list[str]) -> None:
        snapshot = self._refresh_textual_snapshot()
        lang = self.config.lang
        if args and args[0].lower() in {"save", "s"}:
            path = self._export_report_markdown(snapshot)
            if path is None:
                self._record_slash_command_result(
                    "/report",
                    textual_presenters.report_title(lang=lang),
                    textual_presenters.report_no_export_data_markdown(lang=lang),
                    severity="warning",
                    empty=True,
                    action_hint=textual_presenters.report_export_action_hint(lang=lang),
                )
                return
            self._record_slash_command_result(
                "/report",
                textual_presenters.report_title(lang=lang),
                textual_presenters.report_saved_markdown(str(path), lang=lang),
                result_kind="path",
                table_columns=textual_presenters.status_table_columns(lang=lang),
                table_rows=textual_presenters.report_saved_rows(str(path), lang=lang),
            )
            return
        if not snapshot_has_report_data(snapshot):
            self._record_slash_command_result(
                "/report",
                textual_presenters.report_title(lang=lang),
                textual_presenters.report_no_open_data_markdown(lang=lang),
                severity="warning",
                empty=True,
                action_hint=textual_presenters.report_open_action_hint(lang=lang),
            )
            return
        self._record_slash_command_result(
            "/report",
            textual_presenters.report_title(lang=lang),
            textual_presenters.report_opened_markdown(lang=lang),
            table_columns=textual_presenters.status_table_columns(lang=lang),
            table_rows=textual_presenters.report_summary_rows(snapshot, lang=lang),
            start_modal=False,
        )
        self.switch_to("report")

    def _handle_textual_rounds_command(
        self,
        command_name: str,
        args: list[str],
    ) -> None:
        parsed = parse_rounds_args(args, lang=self.config.lang)
        if parsed.rounds is None and not parsed.error:
            self._record_slash_command_result(
                command_name,
                textual_presenters.rounds_title(lang=self.config.lang),
                textual_presenters.session_setting_body(
                    textual_presenters.rounds_current_markdown(
                        self.config.max_deliberation_rounds,
                        lang=self.config.lang,
                    )
                ),
                table_columns=textual_presenters.status_table_columns(
                    lang=self.config.lang
                ),
                table_rows=textual_presenters.rounds_rows(
                    self.config.max_deliberation_rounds,
                    lang=self.config.lang,
                ),
                action_hint=textual_presenters.rounds_change_action_hint(
                    lang=self.config.lang
                ),
            )
            return
        if parsed.error:
            self._record_slash_command_result(
                command_name,
                textual_presenters.rounds_title(lang=self.config.lang),
                parsed.error,
                severity="warning",
                action_hint=parsed.action_hint,
            )
            return
        rounds = parsed.rounds or self.config.max_deliberation_rounds
        self.config.max_deliberation_rounds = rounds
        self._record_slash_command_result(
            command_name,
            textual_presenters.rounds_title(lang=self.config.lang),
            textual_presenters.session_setting_body(
                textual_presenters.rounds_set_markdown(rounds, lang=self.config.lang)
            ),
            table_columns=textual_presenters.status_table_columns(lang=self.config.lang),
            table_rows=textual_presenters.rounds_rows(
                self.config.max_deliberation_rounds,
                lang=self.config.lang,
            ),
        )

    def _handle_textual_agent_command(
        self,
        command_name: str,
        args: list[str],
    ) -> None:
        parsed = parse_agent_args(
            args,
            self.config.agents.keys(),
            lang=self.config.lang,
        )
        if not args:
            self._record_slash_command_result(
                command_name,
                textual_presenters.agent_title(lang=self.config.lang),
                textual_presenters.session_setting_body(
                    textual_presenters.agent_current_settings_markdown(
                        lang=self.config.lang
                    )
                ),
                table_columns=textual_presenters.agent_table_columns(
                    lang=self.config.lang
                ),
                table_rows=textual_presenters.agent_rows(
                    self.config.agents,
                    lang=self.config.lang,
                ),
                action_hint=textual_presenters.agent_change_action_hint(
                    lang=self.config.lang
                ),
            )
            return
        if parsed.error:
            self._record_slash_command_result(
                command_name,
                textual_presenters.agent_title(lang=self.config.lang),
                parsed.error,
                severity="warning",
                table_columns=textual_presenters.agent_table_columns(
                    lang=self.config.lang
                ),
                table_rows=textual_presenters.agent_rows(
                    self.config.agents,
                    lang=self.config.lang,
                ),
            )
            return
        name = parsed.agent_name
        spec = self.config.agents[name]
        spec.enabled = bool(parsed.enabled)
        self._record_slash_command_result(
            command_name,
            textual_presenters.agent_title(lang=self.config.lang),
            textual_presenters.session_setting_body(
                textual_presenters.agent_status_markdown(
                    name,
                    spec.enabled,
                    lang=self.config.lang,
                )
            ),
            table_columns=textual_presenters.agent_table_columns(lang=self.config.lang),
            table_rows=textual_presenters.agent_rows(
                self.config.agents,
                lang=self.config.lang,
            ),
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
                textual_presenters.caveman_title(lang=self.config.lang),
                textual_presenters.session_setting_body(
                    textual_presenters.caveman_current_markdown(
                        mode,
                        self.config.caveman_intensity,
                        lang=self.config.lang,
                    )
                ),
                table_columns=textual_presenters.status_table_columns(
                    lang=self.config.lang
                ),
                table_rows=textual_presenters.caveman_rows(
                    mode,
                    self.config.caveman_intensity,
                    lang=self.config.lang,
                ),
                action_hint=textual_presenters.caveman_change_action_hint(
                    lang=self.config.lang
                ),
            )
            return
        parsed = parse_caveman_args(args, lang=self.config.lang)
        if parsed.error:
            self._record_slash_command_result(
                command_name,
                textual_presenters.caveman_title(lang=self.config.lang),
                parsed.error,
                severity="warning",
                action_hint=parsed.action_hint,
            )
            return
        if parsed.enabled is not None:
            self.config.caveman_mode = parsed.enabled
        if parsed.intensity:
            self.config.caveman_intensity = parsed.intensity
        mode = "on" if self.config.caveman_mode else "off"
        self._record_slash_command_result(
            command_name,
            textual_presenters.caveman_title(lang=self.config.lang),
            textual_presenters.session_setting_body(
                textual_presenters.caveman_set_markdown(
                    mode,
                    self.config.caveman_intensity,
                    lang=self.config.lang,
                )
            ),
            table_columns=textual_presenters.status_table_columns(lang=self.config.lang),
            table_rows=textual_presenters.caveman_rows(
                mode,
                self.config.caveman_intensity,
                lang=self.config.lang,
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
                textual_presenters.target_title(lang=self.config.lang),
                textual_presenters.target_current_markdown(
                    str(current) if current else None,
                    lang=self.config.lang,
                ),
                empty=current is None,
                action_hint=textual_presenters.target_action_hint(lang=self.config.lang),
            )
            return
        action = args[0].lower()
        if action in {"clear", "reset", "none"}:
            outcome = self.workflow_controller.clear_target_workspace()
            self.confirmed_preflight = None
            self._apply_workflow_outcome(outcome)
            self._record_slash_command_result(
                "/target",
                textual_presenters.target_title(lang=self.config.lang),
                textual_presenters.target_cleared_markdown(lang=self.config.lang),
            )
            return
        path = self._resolve_target_path(" ".join(args))
        if self._is_control_repo_target(path):
            self.push_screen(
                TargetWorkspaceConfirmModal(
                    target_path=path,
                    control_repo=self.config.project_dir,
                    lang=self.config.lang,
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
            textual_presenters.target_title(lang=self.config.lang),
            textual_presenters.target_selection_cancelled_markdown(lang=self.config.lang),
            severity="warning",
            empty=True,
            action_hint=textual_presenters.target_control_repo_action_hint(
                lang=self.config.lang
            ),
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
                    textual_presenters.target_title(lang=self.config.lang),
                    textual_presenters.target_not_directory_markdown(
                        str(path),
                        lang=self.config.lang,
                    ),
                    severity="warning",
                    empty=True,
                )
                return
            path.mkdir(parents=True, exist_ok=True)
            resolved = path.resolve()
        except OSError as exc:
            self._record_slash_command_result(
                "/target",
                textual_presenters.target_title(lang=self.config.lang),
                textual_presenters.target_prepare_failed_markdown(
                    str(exc),
                    lang=self.config.lang,
                ),
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
        inside_control_repo = self._is_control_repo_target(resolved)
        self._record_slash_command_result(
            "/target",
            textual_presenters.target_title(lang=self.config.lang),
            textual_presenters.target_workspace_markdown(
                str(resolved),
                lang=self.config.lang,
            ),
            table_columns=textual_presenters.status_table_columns(lang=self.config.lang),
            table_rows=textual_presenters.target_rows(
                str(resolved),
                inside_control_repo=inside_control_repo,
                control_repo_confirmed=control_repo_confirmed,
                lang=self.config.lang,
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
                    textual_presenters.resume_title(lang=self.config.lang),
                    textual_presenters.resume_no_saved_markdown(lang=self.config.lang),
                    empty=True,
                    action_hint=textual_presenters.resume_no_saved_action_hint(
                        lang=self.config.lang
                    ),
                )
                return
            self._record_slash_command_result(
                "/resume",
                textual_presenters.resume_title(lang=self.config.lang),
                textual_presenters.resume_archives_markdown(
                    archives,
                    lang=self.config.lang,
                ),
                table_columns=textual_presenters.resume_archive_table_columns(
                    lang=self.config.lang
                ),
                table_rows=textual_presenters.resume_archive_rows(
                    archives,
                    lang=self.config.lang,
                ),
                action_hint=textual_presenters.resume_pick_action_hint(
                    lang=self.config.lang
                ),
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
                textual_presenters.resume_title(lang=self.config.lang),
                textual_presenters.resume_cancelled_markdown(lang=self.config.lang),
                empty=True,
                action_hint=textual_presenters.resume_cancel_action_hint(
                    lang=self.config.lang
                ),
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
                textual_presenters.resume_title(lang=self.config.lang),
                textual_presenters.workflow_outcome_message_markdown(
                    message,
                    lang=self.config.lang,
                ),
                severity="warning" if failed else "info",
                empty=failed,
                table_columns=textual_presenters.resume_result_table_columns(
                    lang=self.config.lang
                ),
                table_rows=textual_presenters.resume_result_rows(
                    outcome.snapshot,
                    lang=self.config.lang,
                ),
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

    def _handle_textual_answer_command(self, args: list[str]) -> None:
        parsed = parse_answer_args(args, lang=self.config.lang)
        if parsed.error:
            self._record_slash_command_result(
                "/answer",
                textual_presenters.answer_title(lang=self.config.lang),
                parsed.error,
                severity="warning",
                empty=True,
                action_hint=parsed.action_hint,
            )
            return
        if parsed.option_index:
            outcome = self.workflow_controller.answer_question_option(
                parsed.option_index,
                replace=parsed.replace,
            )
        else:
            outcome = self.workflow_controller.answer_question(
                parsed.question_selector,
                parsed.answer,
                replace=parsed.replace,
            )
        message = outcome.message
        if message:
            outcome = replace(outcome, message="")
        self._apply_workflow_outcome(outcome)
        if message:
            self._record_slash_command_result(
                "/answer",
                textual_presenters.answer_title(lang=self.config.lang),
                textual_presenters.workflow_outcome_message_markdown(
                    message,
                    lang=self.config.lang,
                ),
                severity="warning" if message.startswith("No ") else "info",
                empty=message.startswith("No "),
            )

    def _handle_textual_execute_retry_command(self, args: list[str]) -> None:
        selector, package_ids = parse_execute_retry_args(args)
        self.workflow_controller.preview_execution_retry(selector, package_ids)
        snapshot = self._refresh_textual_snapshot()
        if not snapshot.work_package_details:
            self._record_slash_command_result(
                "/execute-retry",
                textual_presenters.execute_retry_title(lang=self.config.lang),
                textual_presenters.execute_retry_no_packages_markdown(
                    lang=self.config.lang
                ),
                severity="warning",
                empty=True,
                action_hint=textual_presenters.execute_retry_no_packages_action_hint(
                    lang=self.config.lang
                ),
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

        lang = self.config.lang
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
            markdown = snapshot_report_markdown(snapshot, lang=self.config.lang)
        else:
            self.notify(
                textual_presenters.report_no_export_data_markdown(lang=lang),
                title=textual_presenters.report_export_unavailable_title(lang=lang),
                severity="warning",
            )
            return None

        filepath.write_text(markdown, encoding="utf-8")
        if self._screens_installed:
            self.get_screen("report", ReportScreen).show_export_path(filepath)
        self.notify(
            textual_presenters.report_saved_notification(str(filepath), lang=lang),
            title=textual_presenters.report_export_complete_title(lang=lang),
        )
        return filepath


def run_textual_app(config: TrinityConfig) -> None:
    """Run the Textual workbench."""
    TrinityTextualApp(config).run()
