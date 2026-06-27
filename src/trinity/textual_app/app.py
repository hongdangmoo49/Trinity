"""Textual application shell for Trinity."""

from __future__ import annotations

from dataclasses import replace
from inspect import Parameter, signature
from pathlib import Path

from textual.app import App
from textual.binding import Binding

from trinity import __version__
from trinity.config import TrinityConfig
from trinity.context.commands import engine_from_config
from trinity.providers.model_discovery import ProviderModelChoice
from trinity.slash_commands import parse_execute_retry_args, parse_slash_command
from trinity.textual_app.command_parsers import (
    parse_agent_args,
    parse_answer_args,
    parse_ask_args,
    parse_caveman_args,
    parse_execute_args,
    parse_report_args,
    parse_resume_args,
    parse_rounds_args,
    parse_target_args,
)
from trinity.textual_app.agent_commands import (
    agent_current_presentation,
    agent_error_presentation,
    agent_update_presentation,
)
from trinity.textual_app.ask_commands import ask_error_presentation
from trinity.textual_app.answer_commands import (
    answer_error_command_presentation,
    answer_result_command_presentation,
    answer_result_presentation,
)
from trinity.textual_app.artifact_commands import artifact_command_presentation
from trinity.textual_app.caveman_commands import (
    caveman_current_presentation,
    caveman_error_presentation,
    caveman_set_presentation,
)
from trinity.textual_app.context_commands import context_command_presentation
from trinity.textual_app.decisions_commands import decisions_command_presentation
from trinity.textual_app.execute_commands import (
    execute_result_presentation,
    execute_retry_no_packages_presentation,
    execution_recovery_snapshot,
)
from trinity.textual_app.help_commands import help_command_presentation
from trinity.textual_app.history_commands import history_command_presentation
from trinity.textual_app.improve_commands import (
    improve_result_command_presentation,
    improve_result_presentation,
)
from trinity.textual_app.local_commands import (
    append_local_command_event,
    local_command_notification,
    local_command_snapshot,
    replace_local_command_result,
    snapshot_with_local_command_results,
)
from trinity.textual_app.memory_commands import memory_command_presentation
from trinity.textual_app.model_discovery import (
    iter_discovered_agent_model_choices,
    merge_discovered_model_choices,
)
from trinity.textual_app.model_settings_commands import (
    model_settings_unavailable_notification,
    model_settings_updated_notification,
)
from trinity.textual_app.packages_commands import packages_command_presentation
from trinity.textual_app.questions_commands import questions_command_presentation
from trinity.textual_app.report_export import (
    export_report_markdown,
)
from trinity.textual_app.report_commands import (
    report_export_complete_notification,
    report_export_unavailable_notification,
    report_open_presentation,
    report_save_presentation,
)
from trinity.textual_app.report_route import prepare_report_route
from trinity.textual_app.resume_commands import (
    resume_archives_presentation,
    resume_cancelled_presentation,
    resume_no_saved_presentation,
    resume_result_command_presentation,
    resume_result_presentation,
    should_continue_resumed_workflow,
)
from trinity.textual_app.route_snapshot import (
    WorkbenchRoute,
    apply_current_route_snapshot,
)
from trinity.textual_app.review_commands import (
    review_matrix_notification_presentation,
    review_repair_blocked_package_ids,
    review_repair_snapshot,
    review_result_command_presentation,
    review_result_presentation,
)
from trinity.textual_app.rounds_commands import (
    rounds_current_presentation,
    rounds_error_presentation,
    rounds_set_presentation,
)
from trinity.textual_app.save_commands import save_command_presentation
from trinity.textual_app.slash_error_commands import (
    slash_syntax_error_presentation,
    unknown_slash_command_presentation,
)
from trinity.textual_app.status_commands import status_command_result
from trinity.textual_app.subtasks_commands import subtasks_command_presentation
from trinity.textual_app.target_commands import (
    target_cancelled_snapshot,
    target_cleared_presentation,
    target_current_presentation,
    target_not_directory_presentation,
    target_prepare_failed_presentation,
    target_workspace_presentation,
)
from trinity.textual_app.screens.execution_matrix import ExecutionMatrixScreen
from trinity.textual_app.screens.nexus import NexusScreen
from trinity.textual_app.screens.report import ReportScreen
from trinity.textual_app.screens.settings import SettingsScreen
from trinity.textual_app.screens.start import StartScreen
from trinity.textual_app.slash_palette import SlashCommandPaletteProvider
from trinity.textual_app.slash_command_router import (
    TextualSlashCommandRoute,
    textual_slash_command_route,
)
from trinity.textual_app.settings import UISettingsStore
from trinity.textual_app.snapshot import (
    LocalCommandSnapshot,
    NexusSnapshotAdapter,
    WORKFLOW_EVENT_DISPLAY_LIMIT,
    WorkflowNexusSnapshot,
)
from trinity.textual_app.snapshot_source import (
    current_textual_snapshot,
    fresh_textual_snapshot,
)
from trinity.textual_app.target_workspace import (
    default_launch_cwd,
    is_control_repo_target,
    prepare_target_workspace,
    resolve_target_path,
    safe_start_target_workspace,
)
from trinity.textual_app.i18n import localize_bindings
from trinity.textual_app.workflow_controller import (
    TextualWorkflowController,
    TextualWorkflowOutcome,
)
from trinity.textual_app.workflow_commands import (
    workflow_command_presentation,
    workflow_outcome_notification_body,
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
    WorkspacePreflight,
    build_workspace_picker,
    build_preflight,
)
from trinity.tui.kitty_compat import install_textual_parser_patch

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
        self.launch_cwd = default_launch_cwd(launch_cwd)
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
        for name, choices in iter_discovered_agent_model_choices(
            self.config.agents.items(),
            use_cache=use_cache,
        ):
            self.call_from_thread(
                self._apply_discovered_model_choices,
                {name: choices},
            )

    def _apply_discovered_model_choices(
        self,
        choices_by_agent: dict[str, tuple[ProviderModelChoice, ...]],
    ) -> None:
        changed_choices = merge_discovered_model_choices(
            self._agent_model_choices,
            choices_by_agent,
        )
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
            self._set_workspace_candidate(event.workspace_candidate, sync_nexus=False)
        nexus = self.get_screen("nexus", NexusScreen)
        nexus.set_initial_prompt(event.prompt)
        nexus.set_agent_selection(event.target_agents, event.agent_model_overrides)
        self._sync_nexus_workspace_candidate()
        target_workspace = safe_start_target_workspace(
            self.workspace_candidate,
            self.config.project_dir,
        )
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
        outcome, message = self._apply_workflow_outcome_without_inline_message(outcome)
        if outcome.execution_recovery_required:
            self._present_execution_recovery(
                "/execute",
                outcome.snapshot,
                message,
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
            presentation = execute_retry_no_packages_presentation(
                lang=self.config.lang
            )
            self.notify(
                presentation.body,
                title=presentation.title,
                severity=presentation.severity,
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
        outcome, message = self._apply_workflow_outcome_without_inline_message(outcome)
        presentation = review_matrix_notification_presentation(
            message,
            lang=self.config.lang,
        )
        if presentation:
            self.notify(
                presentation.body,
                severity=presentation.severity,
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
        package_ids = review_repair_blocked_package_ids(current)
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
                self._apply_execution_screen_state(
                    self.confirmed_preflight,
                    outcome.snapshot,
                )
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
            build_workspace_picker(
                candidate=self.workspace_candidate,
                lang=self.config.lang,
                snapshot=snapshot,
                control_repo_path=self.config.project_dir,
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
        self._set_workspace_candidate(preflight.path, sync_start=True)

    def _on_nexus_workspace_selected(
        self,
        preflight: WorkspacePreflight | None,
    ) -> None:
        if preflight is None:
            return
        if is_control_repo_target(preflight.path, self.config.project_dir):
            self._open_target_workspace_confirm_modal(
                preflight.path,
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
        self._record_local_command_snapshot(
            target_cancelled_snapshot(lang=self.config.lang)
        )

    def _continue_nexus_workspace_selection(
        self,
        preflight: WorkspacePreflight,
        *,
        control_repo_confirmed: bool,
    ) -> None:
        self._set_workspace_candidate(preflight.path, sync_nexus=False)
        self._set_textual_target_workspace(
            preflight.path,
            control_repo_confirmed=control_repo_confirmed,
        )
        self._sync_nexus_workspace_candidate()

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
        if is_control_repo_target(preflight.path, self.config.project_dir):
            self._open_target_workspace_confirm_modal(
                preflight.path,
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

    def _open_target_workspace_confirm_modal(self, path: Path, callback) -> None:
        self.push_screen(
            TargetWorkspaceConfirmModal(
                target_path=path,
                control_repo=self.config.project_dir,
                lang=self.config.lang,
            ),
            callback,
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
        self._record_local_command_snapshot(
            target_cancelled_snapshot(kind="preflight", lang=self.config.lang)
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
        self._apply_execution_screen_state(preflight, outcome.snapshot)
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
            self._apply_execution_screen_state(self.confirmed_preflight, snapshot)
        if outcome.message:
            self.notify(
                workflow_outcome_notification_body(
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
            self._handle_textual_slash_syntax_error(text, parsed.error)
            return
        if not parsed.token:
            return
        if parsed.spec is None:
            self._handle_textual_unknown_slash_command(parsed.token)
            return

        command = parsed.command_id
        args = list(parsed.args)
        route = textual_slash_command_route(command)
        if route is None:
            return
        self._dispatch_textual_slash_command_route(route, parsed.spec.name, args)

    def _dispatch_textual_slash_command_route(
        self,
        route: TextualSlashCommandRoute,
        command_name: str,
        args: list[str],
    ) -> None:
        handler = getattr(self, route.handler_name)
        if route.argument_shape == "none":
            handler()
            return
        if route.argument_shape == "name":
            handler(command_name)
            return
        if route.argument_shape == "args":
            handler(args)
            return
        handler(command_name, args)

    def _handle_textual_slash_syntax_error(self, raw_command: str, error: str) -> None:
        presentation = slash_syntax_error_presentation(error, lang=self.config.lang)
        self._record_slash_command_result(
            raw_command,
            presentation.title,
            presentation.body,
            severity=presentation.severity,
        )

    def _handle_textual_unknown_slash_command(self, command_token: str) -> None:
        presentation = unknown_slash_command_presentation(
            command_token,
            lang=self.config.lang,
        )
        self._record_slash_command_result(
            command_token,
            presentation.title,
            presentation.body,
            severity=presentation.severity,
            table_columns=presentation.table_columns,
            table_rows=presentation.table_rows,
        )

    def _handle_textual_quit_command(self) -> None:
        self.push_screen(
            ConfirmQuitModal(
                running=bool(getattr(self.workflow_controller, "is_running", False)),
                lang=self.config.lang,
            ),
            self._on_quit_confirmed,
        )

    def _handle_textual_help_command(self, command_name: str) -> None:
        presentation = help_command_presentation(lang=self.config.lang)
        self._record_slash_command_result(
            command_name,
            presentation.title,
            presentation.body,
            table_columns=presentation.table_columns,
            table_rows=presentation.table_rows,
        )

    def _handle_textual_status_command(self, command_name: str) -> None:
        snapshot = self._current_textual_snapshot()
        self._show_textual_status(command_name, snapshot)

    def _handle_textual_model_command(self) -> None:
        self._open_model_settings_modal()

    def _handle_textual_workflow_command(self, command_name: str) -> None:
        snapshot = self._refresh_textual_snapshot()
        presentation = workflow_command_presentation(
            snapshot,
            lang=self.config.lang,
        )
        self._record_slash_command_result(
            command_name,
            presentation.title,
            presentation.body,
            table_columns=presentation.table_columns,
            table_rows=presentation.table_rows,
        )

    def _handle_textual_questions_command(
        self,
        command_name: str,
        args: list[str],
    ) -> None:
        snapshot = self._refresh_textual_snapshot()
        select_requested = any(arg.lower() in {"--select", "-s"} for arg in args)
        presentation = questions_command_presentation(
            snapshot,
            select_requested=select_requested,
            lang=self.config.lang,
        )
        self._record_slash_command_result(
            command_name,
            presentation.title,
            presentation.body,
            empty=presentation.empty,
            action_hint=presentation.action_hint,
            table_columns=presentation.table_columns,
            table_rows=presentation.table_rows,
        )

    def _handle_textual_decisions_command(self, command_name: str) -> None:
        snapshot = self._refresh_textual_snapshot()
        presentation = decisions_command_presentation(
            snapshot,
            lang=self.config.lang,
        )
        self._record_slash_command_result(
            command_name,
            presentation.title,
            presentation.body,
            empty=presentation.empty,
            action_hint=presentation.action_hint,
            table_columns=presentation.table_columns,
            table_rows=presentation.table_rows,
        )

    def _handle_textual_packages_command(self, command_name: str) -> None:
        snapshot = self._refresh_textual_snapshot()
        presentation = packages_command_presentation(
            snapshot,
            lang=self.config.lang,
        )
        self._record_slash_command_result(
            command_name,
            presentation.title,
            presentation.body,
            empty=presentation.empty,
            action_hint=presentation.action_hint,
            table_columns=presentation.table_columns,
            table_rows=presentation.table_rows,
        )

    def _handle_textual_subtasks_command(self, command_name: str) -> None:
        snapshot = self._refresh_textual_snapshot()
        presentation = subtasks_command_presentation(
            snapshot,
            lang=self.config.lang,
        )
        self._record_slash_command_result(
            command_name,
            presentation.title,
            presentation.body,
            empty=presentation.empty,
            action_hint=presentation.action_hint,
            table_columns=presentation.table_columns,
            table_rows=presentation.table_rows,
        )

    def _handle_textual_history_command(self, command_name: str) -> None:
        snapshot = self._refresh_textual_snapshot()
        presentation = history_command_presentation(
            snapshot,
            self._local_command_results,
            lang=self.config.lang,
        )
        self._record_slash_command_result(
            command_name,
            presentation.title,
            presentation.body,
            empty=presentation.empty,
            action_hint=presentation.action_hint,
            table_columns=presentation.table_columns,
            table_rows=presentation.table_rows,
        )

    def _handle_textual_save_command(self, command_name: str) -> None:
        presentation = save_command_presentation(lang=self.config.lang)
        self._record_slash_command_result(
            command_name,
            presentation.title,
            presentation.body,
        )

    def _handle_textual_review_command(self, command_name: str, args: list[str]) -> None:
        outcome = self.workflow_controller.request_review(args)
        outcome, message = self._apply_workflow_outcome_without_inline_message(outcome)
        presentation = review_result_presentation(message)
        if presentation:
            result_presentation = review_result_command_presentation(
                presentation,
                outcome.snapshot,
                lang=self.config.lang,
            )
            self._record_slash_command_result(
                command_name,
                result_presentation.title,
                result_presentation.body,
                severity=result_presentation.severity,
                table_columns=result_presentation.table_columns,
                table_rows=result_presentation.table_rows,
                action_hint=result_presentation.action_hint,
            )

    def _handle_textual_improve_command(
        self,
        command_name: str,
        args: list[str],
    ) -> None:
        outcome = self.workflow_controller.request_improvement(args)
        outcome, message = self._apply_workflow_outcome_without_inline_message(outcome)
        presentation = improve_result_presentation(message)
        if presentation:
            result_presentation = improve_result_command_presentation(
                presentation,
                outcome.snapshot,
                lang=self.config.lang,
            )
            self._record_slash_command_result(
                command_name,
                result_presentation.title,
                result_presentation.body,
                severity=result_presentation.severity,
                table_columns=result_presentation.table_columns,
                table_rows=result_presentation.table_rows,
                action_hint=result_presentation.action_hint,
            )

    def _handle_textual_execute_command(
        self,
        command_name: str,
        args: list[str],
    ) -> None:
        parsed_execute = parse_execute_args(args)
        outcome = self.workflow_controller.request_execution(parsed_execute.instruction)
        outcome, message = self._apply_workflow_outcome_without_inline_message(outcome)
        if outcome.execution_recovery_required:
            self._present_execution_recovery(
                command_name,
                outcome.snapshot,
                message,
            )
            return
        if message:
            presentation = execute_result_presentation(message, lang=self.config.lang)
            if presentation is None:
                return
            self._record_slash_command_result(
                command_name,
                presentation.title,
                presentation.body,
                severity=presentation.severity,
                empty=presentation.empty,
                action_hint=presentation.action_hint,
            )
        if outcome.target_workspace_required:
            self._open_execute_workspace_picker(outcome.snapshot)

    def _apply_workflow_outcome_without_inline_message(
        self,
        outcome: TextualWorkflowOutcome,
    ) -> tuple[TextualWorkflowOutcome, str]:
        message = outcome.message
        if message:
            outcome = replace(outcome, message="")
        self._apply_workflow_outcome(outcome)
        return outcome, message

    def _handle_textual_ask_command(self, command_name: str, args: list[str]) -> None:
        parsed = parse_ask_args(
            args,
            self.config.active_agents.keys(),
            lang=self.config.lang,
        )
        if parsed.error:
            presentation = ask_error_presentation(parsed.error, lang=self.config.lang)
            self._record_slash_command_result(
                command_name,
                presentation.title,
                presentation.body,
                severity=presentation.severity,
                empty=presentation.empty,
                action_hint=presentation.action_hint,
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
            target_workspace = safe_start_target_workspace(
                self.workspace_candidate,
                self.config.project_dir,
            )
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
        return current_textual_snapshot(
            active_snapshot=self.active_snapshot,
            controller_snapshot=self.workflow_controller.snapshot,
            persisted_snapshot=self.snapshot_adapter.load_snapshot,
        )

    def _fresh_textual_snapshot(self) -> WorkflowNexusSnapshot:
        """Return the latest persisted/controller snapshot, ignoring stale UI state."""
        return fresh_textual_snapshot(
            controller_snapshot=self.workflow_controller.snapshot,
            persisted_snapshot=self.snapshot_adapter.load_snapshot,
        )

    def _refresh_current_route_from_active_snapshot(self) -> None:
        """Re-apply the active snapshot after Textual finishes a screen switch."""
        if not self._screens_installed:
            return
        snapshot = self._current_textual_snapshot()
        apply_current_route_snapshot(
            self,
            self.current_route,
            snapshot,
            confirmed_preflight=self.confirmed_preflight,
            sync_nexus_workspace_candidate=self._sync_nexus_workspace_candidate,
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
        result = local_command_snapshot(
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
        self._record_local_command_snapshot(
            result,
            start_modal=start_modal,
            notify=True,
        )

    def _record_local_command_snapshot(
        self,
        result: LocalCommandSnapshot,
        *,
        start_modal: bool = True,
        notify: bool = True,
    ) -> None:
        """Persist and render a prepared local slash command result."""
        append_local_command_event(self.config.effective_state_dir, result)
        self._present_local_command_result(
            result,
            start_modal=start_modal,
            notify=notify,
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
            notification = local_command_notification(result, lang=self.config.lang)
            self.notify(
                notification.message,
                title=notification.title,
                severity=notification.severity,
            )

    def _show_textual_status(
        self,
        command: str,
        snapshot: WorkflowNexusSnapshot,
    ) -> None:
        """Show status in the surface appropriate for the current Textual route."""
        result = status_command_result(
            command,
            snapshot,
            lang=self.config.lang,
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
            notification = model_settings_unavailable_notification(
                lang=self.config.lang,
            )
            self.notify(
                notification.message,
                title=notification.title,
                severity=notification.severity,
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
        notification = model_settings_updated_notification(lang=self.config.lang)
        self.notify(
            notification.message,
            title=notification.title,
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
        result = execution_recovery_snapshot(
            command,
            snapshot,
            message,
            lang=self.config.lang,
        )
        self._record_local_command_snapshot(
            result,
            start_modal=False,
        )

    def _present_review_repair_details(self, snapshot: WorkflowNexusSnapshot) -> None:
        result = review_repair_snapshot(
            "/review",
            snapshot,
            lang=self.config.lang,
        )
        self._record_local_command_snapshot(
            result,
            start_modal=False,
        )

    def _handle_textual_context_command(self, command: str) -> None:
        """Show the current session context without reading stale shared.md state."""
        snapshot = self._fresh_textual_snapshot()
        presentation = context_command_presentation(
            command,
            snapshot,
            route=self.current_route,
            lang=self.config.lang,
        )
        if presentation.action == "notify":
            self.notify(
                presentation.body,
                title=presentation.title,
                severity=presentation.severity,
            )
            return
        if presentation.action == "record":
            self._record_slash_command_result(
                presentation.command,
                presentation.title,
                presentation.body,
                severity=presentation.severity,
            )
            return

        result = presentation.result
        if result is None:
            return
        self._local_command_results = replace_local_command_result(
            self._local_command_results,
            result,
        )
        snapshot = snapshot_with_local_command_results(
            snapshot,
            self._local_command_results,
        )
        self.active_snapshot = snapshot
        if presentation.action == "modal":
            self.push_screen(ContextCommandModal(result, lang=self.config.lang))
            return
        self._apply_workflow_outcome(TextualWorkflowOutcome(snapshot))

    def _handle_textual_memory_command(self, args: list[str]) -> None:
        presentation = memory_command_presentation(
            engine_from_config(self.config),
            args,
            target_bytes=self.config.shared_compact_target_bytes,
            recent_records=self.config.memory_recent_records,
            lang=self.config.lang,
        )
        self._record_slash_command_result(
            "/memory",
            presentation.title,
            presentation.body,
            severity=presentation.severity,
            table_columns=presentation.table_columns,
            table_rows=presentation.table_rows,
        )

    def _handle_textual_artifact_command(self, args: list[str]) -> None:
        presentation = artifact_command_presentation(
            engine_from_config(self.config),
            args,
            lang=self.config.lang,
        )
        self._record_slash_command_result(
            "/artifact",
            presentation.title,
            presentation.body,
            severity=presentation.severity,
        )

    def _handle_textual_report_command(self, args: list[str]) -> None:
        snapshot = self._refresh_textual_snapshot()
        lang = self.config.lang
        parsed = parse_report_args(args)
        if parsed.action == "save":
            presentation = report_save_presentation(
                self._export_report_markdown(snapshot),
                lang=lang,
            )
            self._record_slash_command_result(
                "/report",
                presentation.title,
                presentation.body,
                severity=presentation.severity,
                result_kind=presentation.result_kind,
                empty=presentation.empty,
                action_hint=presentation.action_hint,
                table_columns=presentation.table_columns,
                table_rows=presentation.table_rows,
                start_modal=presentation.start_modal,
            )
            return
        presentation = report_open_presentation(snapshot, lang=lang)
        self._record_slash_command_result(
            "/report",
            presentation.title,
            presentation.body,
            severity=presentation.severity,
            result_kind=presentation.result_kind,
            empty=presentation.empty,
            action_hint=presentation.action_hint,
            table_columns=presentation.table_columns,
            table_rows=presentation.table_rows,
            start_modal=presentation.start_modal,
        )
        if presentation.switch_to_report:
            self.switch_to("report")

    def _handle_textual_rounds_command(
        self,
        command_name: str,
        args: list[str],
    ) -> None:
        parsed = parse_rounds_args(args, lang=self.config.lang)
        if parsed.rounds is None and not parsed.error:
            presentation = rounds_current_presentation(
                self.config.max_deliberation_rounds,
                lang=self.config.lang,
            )
            self._record_slash_command_result(
                command_name,
                presentation.title,
                presentation.body,
                table_columns=presentation.table_columns,
                table_rows=presentation.table_rows,
                action_hint=presentation.action_hint,
            )
            return
        if parsed.error:
            presentation = rounds_error_presentation(
                parsed.error,
                parsed.action_hint,
                lang=self.config.lang,
            )
            self._record_slash_command_result(
                command_name,
                presentation.title,
                presentation.body,
                severity=presentation.severity,
                action_hint=presentation.action_hint,
            )
            return
        rounds = parsed.rounds or self.config.max_deliberation_rounds
        self.config.max_deliberation_rounds = rounds
        presentation = rounds_set_presentation(
            self.config.max_deliberation_rounds,
            lang=self.config.lang,
        )
        self._record_slash_command_result(
            command_name,
            presentation.title,
            presentation.body,
            table_columns=presentation.table_columns,
            table_rows=presentation.table_rows,
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
            presentation = agent_current_presentation(
                self.config.agents,
                lang=self.config.lang,
            )
            self._record_slash_command_result(
                command_name,
                presentation.title,
                presentation.body,
                table_columns=presentation.table_columns,
                table_rows=presentation.table_rows,
                action_hint=presentation.action_hint,
            )
            return
        if parsed.error:
            presentation = agent_error_presentation(
                parsed.error,
                self.config.agents,
                lang=self.config.lang,
            )
            self._record_slash_command_result(
                command_name,
                presentation.title,
                presentation.body,
                severity=presentation.severity,
                table_columns=presentation.table_columns,
                table_rows=presentation.table_rows,
            )
            return
        name = parsed.agent_name
        spec = self.config.agents[name]
        spec.enabled = bool(parsed.enabled)
        presentation = agent_update_presentation(
            name,
            spec.enabled,
            self.config.agents,
            lang=self.config.lang,
        )
        self._record_slash_command_result(
            command_name,
            presentation.title,
            presentation.body,
            table_columns=presentation.table_columns,
            table_rows=presentation.table_rows,
        )

    def _handle_textual_caveman_command(
        self,
        command_name: str,
        args: list[str],
    ) -> None:
        if not args:
            mode = "on" if self.config.caveman_mode else "off"
            presentation = caveman_current_presentation(
                mode,
                self.config.caveman_intensity,
                lang=self.config.lang,
            )
            self._record_slash_command_result(
                command_name,
                presentation.title,
                presentation.body,
                table_columns=presentation.table_columns,
                table_rows=presentation.table_rows,
                action_hint=presentation.action_hint,
            )
            return
        parsed = parse_caveman_args(args, lang=self.config.lang)
        if parsed.error:
            presentation = caveman_error_presentation(
                parsed.error,
                parsed.action_hint,
                lang=self.config.lang,
            )
            self._record_slash_command_result(
                command_name,
                presentation.title,
                presentation.body,
                severity=presentation.severity,
                action_hint=presentation.action_hint,
            )
            return
        if parsed.enabled is not None:
            self.config.caveman_mode = parsed.enabled
        if parsed.intensity:
            self.config.caveman_intensity = parsed.intensity
        mode = "on" if self.config.caveman_mode else "off"
        presentation = caveman_set_presentation(
            mode,
            self.config.caveman_intensity,
            lang=self.config.lang,
        )
        self._record_slash_command_result(
            command_name,
            presentation.title,
            presentation.body,
            table_columns=presentation.table_columns,
            table_rows=presentation.table_rows,
        )

    def _handle_textual_target_command(self, args: list[str]) -> None:
        parsed = parse_target_args(args)
        if parsed.action == "current":
            target = getattr(self.workflow_controller, "workflow", None)
            current = None
            if target is not None:
                current = target.session.target_workspace
            presentation = target_current_presentation(
                str(current) if current else None,
                lang=self.config.lang,
            )
            self._record_slash_command_result(
                "/target",
                presentation.title,
                presentation.body,
                empty=presentation.empty,
                action_hint=presentation.action_hint,
            )
            return
        if parsed.action == "clear":
            outcome = self.workflow_controller.clear_target_workspace()
            self.confirmed_preflight = None
            self._apply_workflow_outcome(outcome)
            presentation = target_cleared_presentation(lang=self.config.lang)
            self._record_slash_command_result(
                "/target",
                presentation.title,
                presentation.body,
            )
            return
        path = resolve_target_path(parsed.path_text, self.config.project_dir)
        if is_control_repo_target(path, self.config.project_dir):
            self._open_target_workspace_confirm_modal(
                path,
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
        self._record_local_command_snapshot(
            target_cancelled_snapshot(lang=self.config.lang)
        )

    def _set_textual_target_workspace(
        self,
        path: Path,
        *,
        control_repo_confirmed: bool,
    ) -> None:
        prepared = prepare_target_workspace(path)
        if prepared.error == "not_directory":
            presentation = target_not_directory_presentation(
                prepared.message,
                lang=self.config.lang,
            )
            self._record_slash_command_result(
                "/target",
                presentation.title,
                presentation.body,
                severity=presentation.severity,
                empty=presentation.empty,
            )
            return
        if prepared.error == "os_error":
            presentation = target_prepare_failed_presentation(
                prepared.message,
                lang=self.config.lang,
            )
            self._record_slash_command_result(
                "/target",
                presentation.title,
                presentation.body,
                severity=presentation.severity,
                empty=presentation.empty,
            )
            return
        resolved = prepared.resolved_path
        if resolved is None:
            return

        self._apply_textual_target_workspace(
            resolved,
            control_repo_confirmed=control_repo_confirmed,
        )

    def _apply_textual_target_workspace(
        self,
        resolved: Path,
        *,
        control_repo_confirmed: bool,
    ) -> None:
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
        self._set_workspace_candidate(resolved)
        inside_control_repo = is_control_repo_target(resolved, self.config.project_dir)
        presentation = target_workspace_presentation(
            str(resolved),
            inside_control_repo=inside_control_repo,
            control_repo_confirmed=control_repo_confirmed,
            lang=self.config.lang,
        )
        self._record_slash_command_result(
            "/target",
            presentation.title,
            presentation.body,
            table_columns=presentation.table_columns,
            table_rows=presentation.table_rows,
        )

    def _sync_nexus_workspace_candidate(self) -> None:
        if not self._screens_installed:
            return
        self.get_screen("nexus", NexusScreen).set_workspace_candidate(
            self.workspace_candidate,
        )

    def _set_workspace_candidate(
        self,
        path: Path | None,
        *,
        sync_start: bool = False,
        sync_nexus: bool = True,
    ) -> None:
        self.workspace_candidate = path
        if sync_start:
            self.get_screen("start", StartScreen).set_workspace_candidate(path)
        if sync_nexus:
            self._sync_nexus_workspace_candidate()

    def _handle_textual_resume_command(self, args: list[str]) -> None:
        parsed = parse_resume_args(args)
        if parsed.action == "picker":
            archives = self.workflow_controller.list_resume_options()
            if not archives:
                presentation = resume_no_saved_presentation(lang=self.config.lang)
                self._record_slash_command_result(
                    "/resume",
                    presentation.title,
                    presentation.body,
                    empty=presentation.empty,
                    action_hint=presentation.action_hint,
                )
                return
            presentation = resume_archives_presentation(
                archives,
                lang=self.config.lang,
            )
            self._record_slash_command_result(
                "/resume",
                presentation.title,
                presentation.body,
                table_columns=presentation.table_columns,
                table_rows=presentation.table_rows,
                action_hint=presentation.action_hint,
                start_modal=presentation.start_modal,
            )
            self.push_screen(
                ResumeWorkflowPicker(archives, lang=self.config.lang),
                self._on_resume_archive_selected,
            )
            return
        self._resume_textual_workflow(parsed.selector)

    def _on_resume_archive_selected(self, selector: str | None) -> None:
        if selector is None:
            presentation = resume_cancelled_presentation(lang=self.config.lang)
            self._record_slash_command_result(
                "/resume",
                presentation.title,
                presentation.body,
                empty=presentation.empty,
                action_hint=presentation.action_hint,
            )
            return
        self._resume_textual_workflow(selector)

    def _resume_textual_workflow(self, selector: str) -> None:
        outcome = self.workflow_controller.resume_workflow(selector)
        outcome, message = self._apply_workflow_outcome_without_inline_message(outcome)
        presentation = resume_result_presentation(message)
        if presentation:
            result_presentation = resume_result_command_presentation(
                presentation,
                outcome.snapshot,
                lang=self.config.lang,
            )
            self._record_slash_command_result(
                "/resume",
                result_presentation.title,
                result_presentation.body,
                severity=result_presentation.severity,
                empty=result_presentation.empty,
                table_columns=result_presentation.table_columns,
                table_rows=result_presentation.table_rows,
                start_modal=result_presentation.start_modal,
            )
        if should_continue_resumed_workflow(presentation):
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
            presentation = answer_error_command_presentation(
                parsed.error,
                parsed.action_hint,
                lang=self.config.lang,
            )
            self._record_slash_command_result(
                "/answer",
                presentation.title,
                presentation.body,
                severity=presentation.severity,
                empty=presentation.empty,
                action_hint=presentation.action_hint,
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
        outcome, message = self._apply_workflow_outcome_without_inline_message(outcome)
        presentation = answer_result_presentation(message)
        if presentation:
            result_presentation = answer_result_command_presentation(
                presentation,
                lang=self.config.lang,
            )
            self._record_slash_command_result(
                "/answer",
                result_presentation.title,
                result_presentation.body,
                severity=result_presentation.severity,
                empty=result_presentation.empty,
            )

    def _handle_textual_execute_retry_command(self, args: list[str]) -> None:
        selector, package_ids = parse_execute_retry_args(args)
        self.workflow_controller.preview_execution_retry(selector, package_ids)
        snapshot = self._refresh_textual_snapshot()
        if not snapshot.work_package_details:
            presentation = execute_retry_no_packages_presentation(
                lang=self.config.lang
            )
            self._record_slash_command_result(
                "/execute-retry",
                presentation.title,
                presentation.body,
                severity=presentation.severity,
                empty=presentation.empty,
                action_hint=presentation.action_hint,
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
            self._apply_execution_screen_state(
                self.confirmed_preflight,
                outcome.snapshot,
            )
            self.switch_to("execution")

    def _apply_execution_screen_state(
        self,
        preflight: WorkspacePreflight | None,
        snapshot: WorkflowNexusSnapshot,
    ) -> None:
        execution = self.get_screen("execution", ExecutionMatrixScreen)
        execution.apply_execution_state(preflight, snapshot)

    def _advance_activity_frame(self) -> None:
        if self.current_route == "nexus" and self._screens_installed:
            nexus = self.get_screen("nexus", NexusScreen)
            nexus.advance_activity_frame()

    def switch_to(self, route: WorkbenchRoute) -> None:
        if route == "report" and self._screens_installed:
            report = self.get_screen("report", ReportScreen)
            prepare_report_route(
                report,
                self.active_snapshot or self.snapshot_adapter.load_snapshot(),
                state_dir=self.config.effective_state_dir,
                event_limit=WORKFLOW_EVENT_DISPLAY_LIMIT,
                structured_snapshot=self.active_snapshot,
            )
        if route == "execution" and self._screens_installed:
            apply_current_route_snapshot(
                self,
                route,
                self.active_snapshot
                or self.workflow_controller.snapshot()
                or self.snapshot_adapter.load_snapshot(),
                confirmed_preflight=self.confirmed_preflight,
                sync_nexus_workspace_candidate=self._sync_nexus_workspace_candidate,
                require_execution_preflight=False,
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
        lang = self.config.lang
        filepath = export_report_markdown(
            snapshot,
            state_dir=self.config.effective_state_dir,
            lang=lang,
        )
        if filepath is None:
            notification = report_export_unavailable_notification(lang=lang)
            self.notify(
                notification.message,
                title=notification.title,
                severity=notification.severity,
            )
            return None

        if self._screens_installed:
            self.get_screen("report", ReportScreen).show_export_path(filepath)
        notification = report_export_complete_notification(filepath, lang=lang)
        self.notify(
            notification.message,
            title=notification.title,
        )
        return filepath


def run_textual_app(config: TrinityConfig) -> None:
    """Run the Textual workbench."""
    TrinityTextualApp(config).run()
