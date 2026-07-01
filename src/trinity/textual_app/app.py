"""Textual application shell for Trinity."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Protocol

from textual.app import App
from textual.binding import Binding

from trinity import __version__
from trinity.config import TrinityConfig
from trinity.context.commands import engine_from_config
from trinity.providers.model_discovery import ProviderModelChoice
from trinity.slash_commands import parse_execute_retry_args
from trinity.textual_app.agent_commands import (
    agent_command_presentation,
)
from trinity.textual_app.ask_commands import (
    AskCommandAction,
    AskCommandPresentation,
    AskCommandRun,
    StartSubmissionEffect,
    ask_command_action,
    ask_command_run_effect,
    nexus_follow_up_target_workspace,
    run_ask_command,
    start_submission_effect,
)
from trinity.textual_app.answer_commands import (
    AnswerCommandPresentation,
    AnswerCommandRun,
    answer_message_command_presentation,
    run_answer_command,
)
from trinity.textual_app.artifact_commands import artifact_command_presentation
from trinity.textual_app.caveman_commands import (
    caveman_command_presentation,
)
from trinity.textual_app.context_commands import (
    ContextCommandEffect,
    ContextCommandPresentation,
    context_command_effect,
    context_command_presentation,
)
from trinity.textual_app.controller_calls import call_controller_method
from trinity.textual_app.decisions_commands import decisions_command_presentation
from trinity.textual_app.execute_commands import (
    ExecuteCommandEffect,
    ExecutionRetryRequestEffect,
    execute_command_effect,
    execution_retry_request_effect,
    execution_recovery_snapshot,
)
from trinity.textual_app.command_parsers import parse_execute_args
from trinity.textual_app.help_commands import help_command_presentation
from trinity.textual_app.history_commands import history_command_presentation
from trinity.textual_app.improve_commands import (
    ImproveCommandEffect,
    improve_command_effect,
)
from trinity.textual_app.local_commands import (
    LocalCommandResultEffect,
    append_local_command_event,
    local_command_result_effect,
    local_command_snapshot,
    snapshot_with_local_command_results,
)
from trinity.textual_app.memory_commands import memory_command_presentation
from trinity.textual_app.model_discovery import (
    iter_discovered_agent_model_choices,
    merge_discovered_model_choices,
)
from trinity.textual_app.model_settings_commands import (
    ModelSettingsModalRequest,
    ModelSettingsNotification,
    model_settings_modal_request,
    model_settings_updated_notification,
)
from trinity.textual_app.project_commands import project_command_presentation
from trinity.textual_app.project_context_summary import build_project_context_summary
from trinity.textual_app.packages_commands import packages_command_presentation
from trinity.textual_app.questions_commands import (
    QuestionsCommandPresentation,
    questions_command_presentation_from_args,
)
from trinity.textual_app.report_export import (
    export_report_markdown,
)
from trinity.textual_app.report_commands import (
    ReportCommandPresentation,
    ReportExportEffect,
    report_command_presentation,
    report_export_effect,
)
from trinity.textual_app.report_route import prepare_report_route
from trinity.textual_app.resume_commands import (
    ResumeCommandPresentation,
    resume_cancelled_presentation,
    resume_command_action,
    resume_workflow_effect,
)
from trinity.textual_app.route_snapshot import (
    WorkbenchRoute,
    apply_current_route_snapshot,
)
from trinity.textual_app.review_commands import (
    ReviewRepairAction,
    review_repair_action,
    review_matrix_notification_presentation,
    review_repair_snapshot,
    review_result_command_presentation,
    review_result_presentation,
)
from trinity.textual_app.rounds_commands import (
    rounds_command_presentation,
)
from trinity.textual_app.save_commands import save_command_presentation
from trinity.textual_app.slash_error_commands import (
    slash_syntax_error_presentation,
    unknown_slash_command_presentation,
)
from trinity.textual_app.status_commands import status_command_effect
from trinity.textual_app.subtasks_commands import subtasks_command_presentation
from trinity.textual_app.target_commands import (
    TargetCommandEffect,
    TargetCommandPresentation,
    TargetWorkspaceApplyEffect,
    target_command_action,
    target_command_effect,
    target_cancelled_snapshot,
    target_cleared_presentation,
    target_prepare_result_presentation,
    target_workspace_apply_effect,
)
from trinity.textual_app.target_workspace import safe_start_target_workspace
from trinity.textual_app.screens.execution_matrix import ExecutionMatrixScreen
from trinity.textual_app.screens.nexus import NexusScreen
from trinity.textual_app.screens.report import ReportScreen
from trinity.textual_app.screens.settings import SettingsScreen
from trinity.textual_app.screens.start import StartScreen
from trinity.textual_app.slash_palette import SlashCommandPaletteProvider
from trinity.textual_app.slash_command_router import (
    TextualSlashCommandDispatch,
    TextualSlashCommandRoute,
    textual_slash_command_dispatch,
)
from trinity.textual_app.settings import (
    UISettings,
    UISettingsStore,
    textual_theme_for_mode,
)
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
    TargetWorkspacePreparation,
    WorkspacePreflightContinuation,
    WorkspacePreflightEffect,
    default_launch_cwd,
    is_control_repo_target,
    prepare_target_workspace,
    workspace_preflight_continuation,
    workspace_preflight_effect,
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
from trinity.textual_app.workbench_screens import workbench_screen_specs
from trinity.textual_app.widgets.agent_recipient_model_selector import (
    AgentRecipientModelSelector,
)
from trinity.textual_app.widgets.confirm_quit_modal import ConfirmQuitModal
from trinity.textual_app.widgets.context_modal import ContextCommandModal
from trinity.textual_app.widgets.composer import PromptComposer
from trinity.textual_app.widgets.execution_retry_modal import (
    ExecutionRetryModal,
    ExecutionRetrySelection,
)
from trinity.textual_app.widgets.execution_confirm_modal import (
    ExecutionConfirmModal,
    execution_confirmation_summary,
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
from trinity.textual_app.workspace_labels import (
    provider_cli_setup_label,
    provider_execution_review_policy_label,
)
from trinity.tui.kitty_compat import install_textual_parser_patch


class SlashCommandPresentationPayload(Protocol):
    """Minimum presentation payload recorded as a local slash command."""

    title: str
    body: str


LocalCommandSnapshotOptionValue = (
    str | bool | tuple[str, ...] | tuple[tuple[str, ...], ...]
)


def initial_workspace_candidate(launch_cwd: Path) -> Path:
    """Return the process launch cwd as the default target candidate."""
    return launch_cwd


def _execution_confirmation_risk_items_from_preflight(
    preflight: WorkspacePreflight,
    *,
    lang: str,
) -> tuple[str, ...]:
    items: list[str] = []
    if preflight.requires_dirty_execute_ack:
        changed = preflight.changed_count or 0
        untracked = preflight.untracked_count or 0
        if lang == "ko":
            items.append(
                f"변경사항이 있는 Git 작업 폴더(변경 {changed}, 미추적 {untracked})"
            )
        else:
            items.append(
                f"dirty Git workspace ({changed} changed, {untracked} untracked)"
            )
    items.extend(
        _execution_confirmation_intake_risk_label(warning, lang=lang)
        for warning in preflight.intake_safety_warnings
    )
    return tuple(dict.fromkeys(item for item in items if item.strip()))


def _execution_confirmation_intake_risk_label(warning: str, *, lang: str) -> str:
    labels = {
        "en": {
            "changed_project_intake": "saved analysis changed",
            "missing_new_project_brief": "confirm prompt/work scope",
            "sparse_project_intake": "saved analysis sparse",
            "stale_project_intake": "saved analysis stale",
        },
        "ko": {
            "changed_project_intake": "저장된 분석 변경됨",
            "missing_new_project_brief": "프롬프트/작업 범위 확인 필요",
            "sparse_project_intake": "저장된 분석 부족함",
            "stale_project_intake": "저장된 분석 오래됨",
        },
    }.get(lang, {})
    return labels.get(warning, warning)


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
        padding: 0 2;
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

    #start-screen.start-compact #start-geometry {
        display: none;
    }

    #start-title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        text-align: center;
        color: $accent;
    }

    #start-composer {
        width: 100%;
        height: 8;
        border: round $accent;
        padding: 0 1;
    }

    #start-composer.-commands-open {
        height: 11;
    }

    .ui-density-compact #start-composer {
        height: 6;
    }

    .ui-density-compact #start-composer.-commands-open {
        height: 9;
    }

    .agent-recipient-selector {
        width: 100%;
        height: auto;
        margin-top: 0;
        align-vertical: middle;
    }

    .recipient-label {
        width: auto;
        min-width: 4;
        content-align: left middle;
        color: $text-muted;
        margin-right: 1;
        height: 1;
    }

    .recipient-agent-toggle {
        width: auto;
        min-width: 8;
        height: 1;
        margin-right: 1;
        padding: 0;
        content-align: left middle;
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

    #start-actions {
        width: 100%;
        height: 3;
        align-vertical: middle;
    }

    .ui-density-compact #start-actions {
        height: 2;
    }

    #start-select-workspace {
        width: 22;
        height: 3;
    }

    .ui-density-compact #start-select-workspace {
        height: 2;
    }

    #prompt-textarea {
        height: 1fr;
        border: none;
    }

    #workspace-candidate {
        width: 1fr;
        min-width: 0;
        height: 3;
        margin-right: 1;
        color: $text-muted;
        content-align: left middle;
    }

    .ui-density-compact #workspace-candidate {
        height: 2;
    }

    #nexus-screen {
        width: 100%;
        height: 1fr;
        padding: 0 1;
    }

    #provider-strip {
        width: 100%;
        height: 5;
        layout: grid;
        grid-gutter: 1;
    }

    .ui-density-compact #provider-strip {
        height: 4;
    }

    .provider-strip-1 {
        grid-size: 1 1;
    }

    .provider-strip-2 {
        grid-size: 2 1;
    }

    .provider-strip-3 {
        grid-size: 3 1;
    }

    .provider-panel {
        height: 5;
        border: round $accent;
        padding: 0 1;
    }

    .ui-density-compact .provider-panel {
        height: 4;
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

    .ui-density-compact #central-agent {
        padding: 0 1;
    }

    #central-agent.central-running {
        border: heavy $warning;
    }

    #nexus-main {
        height: 1fr;
        margin: 1 0;
    }

    .ui-density-compact #nexus-main {
        margin: 0;
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
        max-height: 95%;
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
        height: 95%;
        max-height: 95%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }

    #context-command-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #context-command-content {
        height: 1fr;
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
        height: 95%;
        max-height: 95%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }

    #local-command-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #local-command-content {
        height: 1fr;
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

    .ui-density-compact #nexus-question-panel {
        height: 9;
        margin-top: 0;
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

    #nexus-target-workspace {
        width: 1fr;
        min-width: 0;
        height: 1;
        margin-top: 1;
        content-align: left middle;
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

    .ui-density-compact .settings-section-title {
        margin-top: 0;
        margin-bottom: 0;
    }

    .settings-row {
        width: 100%;
        max-width: 96;
        height: 3;
    }

    .ui-density-compact .settings-row {
        height: 2;
    }

    .settings-row Label {
        width: 26;
        content-align: left middle;
    }

    .settings-row Select {
        width: 1fr;
        min-width: 28;
    }

    #theme-preview {
        width: 100%;
        max-width: 96;
        height: auto;
        max-height: 14;
        overflow-y: auto;
        border: round $accent;
        margin-top: 1;
        padding: 1 2;
    }

    .ui-density-compact #theme-preview {
        max-height: 10;
        margin-top: 0;
        padding: 0 1;
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

    .ui-density-compact #execution-screen {
        padding: 0;
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

    .ui-density-compact #execution-summary {
        margin-top: 0;
    }

    #execution-package-list {
        height: 13;
        margin-top: 1;
        border: round $primary;
        padding: 0 1;
    }

    .ui-density-compact #execution-package-list {
        height: 12;
        margin-top: 0;
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

    .ui-density-compact #execution-log {
        height: 8;
        margin-top: 0;
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

    .ui-density-compact #report-screen {
        padding: 0 1;
    }

    #report-header {
        height: 4;
        margin-bottom: 1;
    }

    .ui-density-compact #report-header {
        height: 3;
        margin-bottom: 0;
    }

    #report-title {
        text-style: bold;
        color: $accent;
    }

    #report-export-btn {
        margin-top: 1;
    }

    .ui-density-compact #report-export-btn {
        margin-top: 0;
    }

    #report-export-status {
        color: $text-muted;
    }

    #report-body {
        height: 1fr;
        border: round $primary;
        padding: 1 2;
    }

    .ui-density-compact #report-body {
        padding: 0 1;
    }

    #nexus-composer {
        width: 100%;
        height: 7;
        border: round $accent;
        padding: 0 1;
    }

    #nexus-composer.-commands-open {
        dock: bottom;
        height: 11;
    }

    #prompt-command-palette {
        display: none;
        width: 1fr;
        max-height: 7;
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

    .ui-color-profile-truecolor #start-geometry,
    .ui-color-profile-truecolor #start-title,
    .ui-color-profile-truecolor .recipient-agent-toggle-selected,
    .ui-color-profile-truecolor .command-option-selected,
    .ui-color-profile-truecolor .command-option-first,
    .ui-color-profile-truecolor #settings-title {
        color: #5ce1e6;
    }

    .ui-color-profile-truecolor #start-composer,
    .ui-color-profile-truecolor #nexus-composer,
    .ui-color-profile-truecolor #prompt-command-palette,
    .ui-color-profile-truecolor #theme-preview {
        border: round #5ce1e6;
    }

    .ui-color-profile-256color #start-geometry,
    .ui-color-profile-256color #start-title,
    .ui-color-profile-256color .recipient-agent-toggle-selected,
    .ui-color-profile-256color .command-option-selected,
    .ui-color-profile-256color .command-option-first,
    .ui-color-profile-256color #settings-title {
        color: cyan;
    }

    .ui-color-profile-256color #start-composer,
    .ui-color-profile-256color #nexus-composer,
    .ui-color-profile-256color #prompt-command-palette,
    .ui-color-profile-256color #theme-preview {
        border: round cyan;
    }

    .ui-color-profile-ascii-safe #start-geometry,
    .ui-color-profile-ascii-safe #start-title,
    .ui-color-profile-ascii-safe .recipient-agent-toggle-selected,
    .ui-color-profile-ascii-safe .command-option-selected,
    .ui-color-profile-ascii-safe .command-option-first,
    .ui-color-profile-ascii-safe .provider-status,
    .ui-color-profile-ascii-safe #settings-title {
        color: $text;
    }

    .ui-color-profile-ascii-safe #start-composer,
    .ui-color-profile-ascii-safe #nexus-composer,
    .ui-color-profile-ascii-safe #prompt-command-palette,
    .ui-color-profile-ascii-safe .provider-panel,
    .ui-color-profile-ascii-safe #workflow-inspector,
    .ui-color-profile-ascii-safe #nexus-question-panel,
    .ui-color-profile-ascii-safe #theme-preview {
        border: round white;
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
        self._init_textual_navigation_state(config, launch_cwd)
        self._init_textual_runtime_state(config, workflow_controller)

    def _init_textual_navigation_state(
        self,
        config: TrinityConfig,
        launch_cwd: Path | None,
    ) -> None:
        self.config = config
        self.current_route: WorkbenchRoute = "start"
        self.initial_prompt: str | None = None
        self.launch_cwd = default_launch_cwd(launch_cwd)
        self.workspace_candidate: Path | None = initial_workspace_candidate(self.launch_cwd)
        self.snapshot_adapter = NexusSnapshotAdapter(config)
        self.active_snapshot: WorkflowNexusSnapshot | None = None
        self.settings_store = UISettingsStore(config.effective_state_dir)
        self.ui_settings = self.settings_store.load()
        self.theme = textual_theme_for_mode(self.ui_settings.theme_mode)
        self.confirmed_preflight: WorkspacePreflight | None = None

    def _init_textual_runtime_state(
        self,
        config: TrinityConfig,
        workflow_controller: TextualWorkflowController | None,
    ) -> None:
        self.workflow_controller = workflow_controller or TextualWorkflowController(config)
        self._screens_installed = False
        self._workflow_polling_started = False
        self._model_discovery_started = False
        self._agent_model_choices: dict[str, tuple[ProviderModelChoice, ...]] = {}
        self._local_command_results: list[LocalCommandSnapshot] = []
        self._pending_execute_retry: ExecutionRetrySelection | None = None

    def on_mount(self) -> None:
        self._apply_ui_settings(self.ui_settings)
        self._install_workbench_screens()
        self.current_route = "start"
        self.push_screen("start")
        self._start_model_discovery()

    def _install_workbench_screens(self) -> None:
        if self._screens_installed:
            return

        for spec in workbench_screen_specs(
            self.config,
            self.settings_store,
            self.workspace_candidate,
            start_prompt="",
        ):
            self.install_screen(spec.screen, spec.route)

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
            self.config.active_agents.items(),
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
        changed_choices = self._merge_discovered_model_choices(choices_by_agent)
        if not changed_choices:
            return
        self._sync_discovered_model_choice_surfaces(changed_choices)

    def _merge_discovered_model_choices(
        self,
        choices_by_agent: dict[str, tuple[ProviderModelChoice, ...]],
    ) -> dict[str, tuple[ProviderModelChoice, ...]]:
        return merge_discovered_model_choices(
            self._agent_model_choices,
            choices_by_agent,
        )

    def _sync_discovered_model_choice_surfaces(
        self,
        changed_choices: dict[str, tuple[ProviderModelChoice, ...]],
    ) -> None:
        for screen_name, screen_type in (
            ("start", StartScreen),
            ("nexus", NexusScreen),
            ("settings", SettingsScreen),
        ):
            screen = self.get_screen(screen_name, screen_type)
            screen.set_agent_model_choices(changed_choices)
        self._sync_discovered_model_settings_modal(changed_choices)

    def _sync_discovered_model_settings_modal(
        self,
        changed_choices: dict[str, tuple[ProviderModelChoice, ...]],
    ) -> None:
        if isinstance(self.screen, ModelSettingsModal):
            self.screen.set_model_choices(changed_choices)

    def on_settings_screen_applied(self, event: SettingsScreen.Applied) -> None:
        event.stop()
        self.ui_settings = self.settings_store.load()
        self._apply_ui_settings(self.ui_settings)
        self.get_screen("start", StartScreen).sync_ui_settings()
        self._sync_configured_agent_model_selectors()
        self._refresh_agent_enabled_snapshot()

    def _apply_ui_settings(self, settings: UISettings) -> None:
        self.theme = textual_theme_for_mode(settings.theme_mode)
        for profile in ("truecolor", "256color", "ascii-safe"):
            self.set_class(
                settings.color_profile == profile,
                f"ui-color-profile-{profile}",
            )
        self.set_class(settings.density == "compact", "ui-density-compact")
        self.set_class(settings.motion == "reduced", "ui-motion-reduced")
        self.set_class(settings.unicode_rendering == "unicode", "ui-unicode-rendering")

    def _sync_configured_agent_model_selectors(self) -> None:
        selections = {
            name: spec.model or "default"
            for name, spec in self.config.agents.items()
        }
        for screen_name, screen_type in (
            ("start", StartScreen),
            ("nexus", NexusScreen),
        ):
            screen = self.get_screen(screen_name, screen_type)
            if screen.is_mounted:
                screen.query_one(AgentRecipientModelSelector).set_model_selections(
                    selections,
                )

    def _sync_agent_enabled_surfaces(self) -> None:
        for screen_name, screen_type in (
            ("start", StartScreen),
            ("nexus", NexusScreen),
        ):
            screen = self.get_screen(screen_name, screen_type)
            if screen.is_mounted:
                screen.query_one(AgentRecipientModelSelector).sync_agent_states()
        settings = self.get_screen("settings", SettingsScreen)
        if settings.is_mounted:
            settings.sync_agent_enabled_states()

    def _refresh_agent_enabled_snapshot(self) -> None:
        snapshot = snapshot_with_local_command_results(
            self._fresh_textual_snapshot(),
            self._local_command_results,
        )
        self._apply_workflow_outcome(TextualWorkflowOutcome(snapshot))

    def on_start_screen_submitted(self, event: StartScreen.Submitted) -> None:
        event.stop()
        effect = start_submission_effect(
            prompt=event.prompt,
            event_workspace_candidate=event.workspace_candidate,
            current_workspace_candidate=self.workspace_candidate,
            target_agents=event.target_agents,
            agent_model_overrides=event.agent_model_overrides,
            project_dir=self.config.project_dir,
        )
        self._apply_start_submission_effect(effect)

    def _apply_start_submission_effect(self, effect: StartSubmissionEffect) -> None:
        self._prepare_start_submission_ui(effect)
        outcome = self._run_start_submission(effect)
        self._remember_confirmed_target_preflight(
            effect.target_workspace,
            outcome.snapshot,
        )
        self._apply_workflow_outcome(outcome)
        self.switch_to("nexus")

    def _prepare_start_submission_ui(self, effect: StartSubmissionEffect) -> None:
        self.initial_prompt = effect.prompt
        if effect.workspace_candidate_to_set is not None:
            self._set_workspace_candidate(
                effect.workspace_candidate_to_set,
                sync_nexus=False,
            )
        nexus = self.get_screen("nexus", NexusScreen)
        nexus.set_initial_prompt(effect.prompt)
        nexus.set_agent_selection(
            effect.target_agents,
            effect.agent_model_overrides,
        )
        self._sync_nexus_workspace_candidate()

    def _run_start_submission(self, effect: StartSubmissionEffect):
        return call_controller_method(
            self.workflow_controller.start_prompt,
            effect.prompt,
            target_workspace=effect.target_workspace,
            target_agents=effect.target_agents,
            agent_model_overrides=effect.agent_model_overrides,
        )

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
        self._open_workspace_command()

    def on_nexus_screen_follow_up_submitted(
        self,
        event: NexusScreen.FollowUpSubmitted,
    ) -> None:
        event.stop()
        target = nexus_follow_up_target_workspace(
            self.active_snapshot
            or self.workflow_controller.snapshot()
            or self.snapshot_adapter.load_snapshot(),
            self.workspace_candidate,
            self.config.project_dir,
        )
        if target is not None:
            target_outcome = self.workflow_controller.set_target_workspace(target)
            self._remember_confirmed_target_preflight(target, target_outcome.snapshot)
            self._set_workspace_candidate(target, sync_start=True)
        outcome = call_controller_method(
            self.workflow_controller.submit_follow_up,
            event.text,
            target_agents=event.target_agents,
            agent_model_overrides=event.agent_model_overrides,
        )
        self._apply_workflow_outcome(outcome)
        if outcome.target_workspace_required:
            self._open_execute_workspace_picker(outcome.snapshot)

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
        self._open_provider_inspector(event.snapshot)

    def _open_provider_inspector(
        self,
        snapshot: WorkflowNexusSnapshot | None = None,
    ) -> None:
        snapshot = (
            snapshot
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
        snapshot = (
            event.snapshot
            or self.active_snapshot
            or self.workflow_controller.snapshot()
            or self.snapshot_adapter.load_snapshot()
        )
        if self._maybe_open_execution_confirmation(
            snapshot,
            command_name="/execute",
            instruction="",
            slash_command=False,
        ):
            return
        self._request_nexus_execution()

    def _request_nexus_execution(self, instruction: str = "") -> None:
        outcome = self.workflow_controller.request_execution(instruction)
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

    def on_execution_matrix_screen_retry_requested(
        self,
        event: ExecutionMatrixScreen.RetryRequested,
    ) -> None:
        event.stop()
        selector = event.selector
        package_ids = tuple(event.package_ids)
        self.workflow_controller.preview_execution_retry(selector, list(package_ids))
        snapshot = self.workflow_controller.snapshot() or event.snapshot
        effect = execution_retry_request_effect(
            snapshot,
            selector,
            package_ids,
            lang=self.config.lang,
        )
        self._apply_execution_retry_request_effect(effect)

    def _apply_execution_retry_request_effect(
        self,
        effect: ExecutionRetryRequestEffect,
    ) -> None:
        self._apply_workflow_outcome(TextualWorkflowOutcome(effect.snapshot))
        if not effect.show_retry_modal:
            presentation = effect.no_packages_presentation
            if presentation is None:
                return
            self.notify(
                presentation.body,
                title=presentation.title,
                severity=presentation.severity,
            )
            return
        self._open_execution_retry_modal(effect)

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
        repair_action = review_repair_action(action, current)
        self._apply_review_repair_action(current, repair_action)

    def _apply_review_repair_action(
        self,
        snapshot: WorkflowNexusSnapshot,
        action: ReviewRepairAction,
    ) -> None:
        if action.kind == "open_review":
            self._present_review_repair_details(snapshot)
            return
        if action.kind == "retry_once":
            self._retry_review_repair_action(action)
            return
        self._apply_review_repair_completion_action(action)

    def _apply_review_repair_completion_action(
        self,
        action: ReviewRepairAction,
    ) -> None:
        if action.kind == "mark_done":
            outcome = self.workflow_controller.accept_blocked_review_repairs()
        elif action.kind == "stop":
            outcome = self.workflow_controller.stop_blocked_review_repairs()
        else:
            return
        self._apply_workflow_outcome(outcome)

    def _retry_review_repair_action(self, action: ReviewRepairAction) -> None:
        outcome = self.workflow_controller.retry_blocked_review_repairs()
        if outcome.target_workspace_required:
            self._pending_execute_retry = ExecutionRetrySelection(
                "custom",
                action.package_ids,
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

    def _open_execute_workspace_picker(self, snapshot: WorkflowNexusSnapshot) -> None:
        self._open_workspace_picker(snapshot, self._on_workspace_preflight)

    def _maybe_open_execution_confirmation(
        self,
        snapshot: WorkflowNexusSnapshot,
        *,
        command_name: str,
        instruction: str,
        slash_command: bool,
    ) -> bool:
        if not self._execution_confirmation_eligible(snapshot, instruction):
            return False
        context_summary = build_project_context_summary(
            self.config.effective_state_dir,
            snapshot.target_workspace,
            lang=self.config.lang,
        )
        summary = execution_confirmation_summary(
            snapshot,
            workspace_context=context_summary.workspace_context,
            context_items=context_summary.items,
            instruction=instruction,
            risk_items=self._execution_confirmation_risk_items(snapshot),
        )
        self.push_screen(
            ExecutionConfirmModal(summary, lang=self.config.lang),
            lambda confirmed: self._on_execution_confirmation(
                confirmed,
                command_name=command_name,
                instruction=instruction,
                slash_command=slash_command,
            ),
        )
        return True

    def _on_execution_confirmation(
        self,
        confirmed: bool | None,
        *,
        command_name: str,
        instruction: str,
        slash_command: bool,
    ) -> None:
        if not confirmed:
            return
        if slash_command:
            self._run_textual_execute_command(command_name, instruction)
            return
        self._request_nexus_execution(instruction)

    def _execution_confirmation_eligible(
        self,
        snapshot: WorkflowNexusSnapshot,
        instruction: str,
    ) -> bool:
        if self.current_route != "nexus":
            return False
        if self._execute_instruction_bypasses_confirmation(instruction):
            return False
        if snapshot.state != "blueprint_ready":
            return False
        if not str(snapshot.target_workspace or "").strip():
            return False
        summary = execution_confirmation_summary(snapshot, instruction=instruction)
        return summary.has_executable_packages

    @staticmethod
    def _execute_instruction_bypasses_confirmation(instruction: str) -> bool:
        normalized = instruction.strip().lower()
        return normalized in {
            "retry",
            "retry-interrupted",
            "recovery retry",
            "mark-interrupted",
            "mark interrupted",
            "mark",
            "abort",
            "abort-execution",
            "abort execution",
        }

    def _execution_confirmation_risk_items(
        self,
        snapshot: WorkflowNexusSnapshot,
    ) -> tuple[str, ...]:
        target = str(snapshot.target_workspace or "").strip()
        if not target:
            return ()
        preflight = build_preflight(
            Path(target),
            snapshot,
            project_intake_state_dir=self.config.effective_state_dir,
        )
        return _execution_confirmation_risk_items_from_preflight(
            preflight,
            lang=self.config.lang,
        )

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
                project_intake_state_dir=self.config.effective_state_dir,
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
        if self._open_nexus_workspace_confirm_if_needed(preflight):
            return
        self._continue_nexus_workspace_selection(
            preflight,
            control_repo_confirmed=False,
        )

    def _open_nexus_workspace_confirm_if_needed(
        self,
        preflight: WorkspacePreflight,
    ) -> bool:
        if not is_control_repo_target(preflight.path, self.config.project_dir):
            return False
        self._open_target_workspace_confirm_modal(
            preflight.path,
            lambda confirmed: self._on_nexus_workspace_selected_confirmed(
                preflight,
                confirmed,
            ),
        )
        return True

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
        self.confirmed_preflight = build_preflight(
            path,
            snapshot,
            project_intake_state_dir=self.config.effective_state_dir,
        )

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
        continuation = workspace_preflight_continuation(
            preflight,
            control_repo_confirmed=control_repo_confirmed,
            pending_retry=self._pending_execute_retry,
        )
        self._pending_execute_retry = None
        self._continue_workspace_preflight_plan(continuation)

    def _continue_workspace_preflight_plan(
        self,
        continuation: WorkspacePreflightContinuation,
    ) -> None:
        preflight = continuation.preflight
        self.confirmed_preflight = preflight
        outcome = self._run_workspace_preflight_continuation(continuation)
        self._apply_workflow_outcome(outcome)
        self._apply_workspace_preflight_effect(
            workspace_preflight_effect(preflight, outcome)
        )

    def _run_workspace_preflight_continuation(
        self,
        continuation: WorkspacePreflightContinuation,
    ) -> TextualWorkflowOutcome:
        preflight = continuation.preflight
        self.workflow_controller.set_target_workspace(
            preflight.path,
            control_repo_confirmed=continuation.control_repo_confirmed,
        )
        if continuation.use_retry:
            return self.workflow_controller.confirm_execution_retry(
                continuation.retry_selector,
                list(continuation.retry_package_ids),
            )
        return self.workflow_controller.request_execution()

    def _apply_workspace_preflight_effect(
        self,
        effect: WorkspacePreflightEffect,
    ) -> None:
        if effect.execution_recovery_snapshot is not None:
            self._present_execution_recovery(
                "/execute",
                effect.execution_recovery_snapshot,
                effect.execution_recovery_message,
            )
            return
        if effect.show_execution:
            self._apply_execution_screen_state(
                effect.execution_preflight,
                effect.execution_snapshot,
            )
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
        elif self._workflow_controller_is_running():
            self._advance_activity_frame()

    def _workflow_controller_is_running(self) -> bool:
        return bool(getattr(self.workflow_controller, "is_running", False))

    def _apply_workflow_outcome(self, outcome: TextualWorkflowOutcome) -> None:
        snapshot = self._store_workflow_outcome_snapshot(outcome)
        self._apply_workflow_outcome_routes(outcome, snapshot)
        self._notify_workflow_outcome(outcome)
        if outcome.running:
            self._ensure_workflow_polling()

    def _store_workflow_outcome_snapshot(
        self,
        outcome: TextualWorkflowOutcome,
    ) -> WorkflowNexusSnapshot:
        snapshot = snapshot_with_local_command_results(
            outcome.snapshot,
            self._local_command_results,
        )
        self.active_snapshot = snapshot
        return snapshot

    def _apply_workflow_outcome_routes(
        self,
        outcome: TextualWorkflowOutcome,
        snapshot: WorkflowNexusSnapshot,
    ) -> None:
        self._apply_nexus_workflow_outcome(outcome, snapshot)
        self._apply_execution_workflow_outcome(snapshot)

    def _apply_nexus_workflow_outcome(
        self,
        outcome: TextualWorkflowOutcome,
        snapshot: WorkflowNexusSnapshot,
    ) -> None:
        if self._screens_installed and self.current_route == "nexus":
            nexus = self.get_screen("nexus", NexusScreen)
            nexus.apply_snapshot(snapshot)
            if outcome.running:
                nexus.advance_activity_frame()

    def _apply_execution_workflow_outcome(
        self,
        snapshot: WorkflowNexusSnapshot,
    ) -> None:
        if self.current_route == "execution" and self.confirmed_preflight is not None:
            self._apply_execution_screen_state(self.confirmed_preflight, snapshot)

    def _notify_workflow_outcome(self, outcome: TextualWorkflowOutcome) -> None:
        if outcome.message:
            self.notify(
                workflow_outcome_notification_body(
                    outcome.message,
                    lang=self.config.lang,
                )
            )

    def _handle_textual_slash_command(self, text: str) -> None:
        """Execute a Trinity slash command without routing it as model input."""
        dispatch = textual_slash_command_dispatch(text)
        if dispatch is None:
            return
        self._apply_textual_slash_command_dispatch(dispatch)

    def _apply_textual_slash_command_dispatch(
        self,
        dispatch: TextualSlashCommandDispatch,
    ) -> None:
        if self._record_textual_slash_command_error(dispatch):
            return
        if dispatch.route is None:
            return
        self._dispatch_textual_slash_command_route(
            dispatch.route,
            dispatch.command_name,
            list(dispatch.args),
        )

    def _record_textual_slash_command_error(
        self,
        dispatch: TextualSlashCommandDispatch,
    ) -> bool:
        if dispatch.syntax_error:
            self._handle_textual_slash_syntax_error(
                dispatch.raw_command,
                dispatch.syntax_error,
            )
            return True
        if dispatch.unknown_token:
            self._handle_textual_unknown_slash_command(dispatch.unknown_token)
            return True
        return False

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
                running=self._workflow_controller_is_running(),
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

    def _handle_textual_providers_command(self) -> None:
        self._open_provider_inspector(self._current_textual_snapshot())

    def _handle_textual_workspace_command(self) -> None:
        self._open_workspace_command()

    def _handle_textual_settings_command(self) -> None:
        self.action_go_settings()

    def _handle_textual_project_command(
        self,
        command_name: str,
        args: list[str],
    ) -> None:
        if args:
            self._record_project_command_argument_error(command_name, args[0])
            return
        snapshot = self._current_textual_snapshot()
        presentation = project_command_presentation(
            self.config.effective_state_dir,
            self.config.active_agents,
            lang=self.config.lang,
            target_workspace=self._project_command_target_workspace(snapshot),
        )
        self._record_slash_command_result(
            command_name,
            presentation.title,
            presentation.body,
            severity=presentation.severity,
            action_hint=presentation.action_hint,
        )

    def _record_project_command_argument_error(
        self,
        command_name: str,
        action: str,
    ) -> None:
        if self.config.lang == "ko":
            title = "프로젝트 명령 인자 미지원"
            body = (
                f"`/project {action}`는 지원하지 않습니다.\n\n"
                "작업 폴더는 `/target <path>`로 지정하거나 `/workspace`에서 선택하세요."
            )
        else:
            title = "Project Command Takes No Arguments"
            body = (
                f"`/project {action}` is not supported.\n\n"
                "Use `/target <path>` to set a target or `/workspace` to browse."
            )
        self._record_slash_command_result(
            command_name,
            title,
            body,
            severity="warning",
        )

    def _open_workspace_command(self) -> None:
        if self.current_route == "start":
            self._open_workspace_picker(
                WorkflowNexusSnapshot(),
                self._on_workspace_candidate_selected,
                intent="select",
            )
            return
        snapshot = self._current_textual_snapshot()
        self._open_workspace_picker(
            snapshot,
            self._on_nexus_workspace_selected,
            intent="select",
        )

    def _project_command_target_workspace(
        self,
        snapshot: WorkflowNexusSnapshot,
    ) -> Path | None:
        if self.current_route == "start":
            return safe_start_target_workspace(
                self.workspace_candidate,
                self.config.project_dir,
            )
        return nexus_follow_up_target_workspace(
            snapshot,
            self.workspace_candidate,
            self.config.project_dir,
        )

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
        presentation = questions_command_presentation_from_args(
            args,
            snapshot,
            lang=self.config.lang,
        )
        self._record_questions_command_presentation(command_name, presentation)

    def _record_questions_command_presentation(
        self,
        command_name: str,
        presentation: QuestionsCommandPresentation,
    ) -> None:
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
        if presentation is not None:
            self._record_slash_command_presentation(
                command_name,
                review_result_command_presentation(
                    presentation,
                    outcome.snapshot,
                    lang=self.config.lang,
                ),
            )

    def _record_slash_command_presentation(
        self,
        command_name: str,
        presentation: SlashCommandPresentationPayload,
    ) -> None:
        self._record_slash_command_result(
            command_name,
            presentation.title,
            presentation.body,
            severity=getattr(presentation, "severity", "info"),
            empty=getattr(presentation, "empty", False),
            result_kind=getattr(presentation, "result_kind", "markdown"),
            table_columns=getattr(presentation, "table_columns", ()),
            table_rows=getattr(presentation, "table_rows", ()),
            action_hint=getattr(presentation, "action_hint", ""),
        )

    def _handle_textual_improve_command(
        self,
        command_name: str,
        args: list[str],
    ) -> None:
        outcome = self.workflow_controller.request_improvement(args)
        outcome, message = self._apply_workflow_outcome_without_inline_message(outcome)
        effect = improve_command_effect(
            message,
            outcome.snapshot,
            lang=self.config.lang,
        )
        self._apply_textual_improve_effect(command_name, effect)

    def _apply_textual_improve_effect(
        self,
        command_name: str,
        effect: ImproveCommandEffect,
    ) -> None:
        if effect.presentation is None:
            return
        presentation = effect.presentation
        self._record_slash_command_result(
            command_name,
            presentation.title,
            presentation.body,
            severity=presentation.severity,
            table_columns=presentation.table_columns,
            table_rows=presentation.table_rows,
            action_hint=presentation.action_hint,
        )

    def _handle_textual_execute_command(
        self,
        command_name: str,
        args: list[str],
    ) -> None:
        parsed_execute = parse_execute_args(args)
        if self._maybe_open_execution_confirmation(
            self._current_textual_snapshot(),
            command_name=command_name,
            instruction=parsed_execute.instruction,
            slash_command=True,
        ):
            return
        self._run_textual_execute_command(command_name, parsed_execute.instruction)

    def _run_textual_execute_command(
        self,
        command_name: str,
        instruction: str,
    ) -> None:
        outcome = self.workflow_controller.request_execution(instruction)
        outcome, message = self._apply_workflow_outcome_without_inline_message(outcome)
        self._apply_textual_execute_effect(
            command_name,
            execute_command_effect(outcome, message, lang=self.config.lang),
        )

    def _apply_textual_execute_effect(
        self,
        command_name: str,
        effect: ExecuteCommandEffect,
    ) -> None:
        if effect.execution_recovery_snapshot is not None:
            self._apply_textual_execute_recovery_effect(command_name, effect)
            return
        self._apply_textual_execute_presentation_effect(command_name, effect)
        self._apply_textual_execute_workspace_picker_effect(effect)

    def _apply_textual_execute_recovery_effect(
        self,
        command_name: str,
        effect: ExecuteCommandEffect,
    ) -> None:
        if effect.execution_recovery_snapshot is None:
            return
        self._present_execution_recovery(
            command_name,
            effect.execution_recovery_snapshot,
            effect.execution_recovery_message,
        )

    def _apply_textual_execute_presentation_effect(
        self,
        command_name: str,
        effect: ExecuteCommandEffect,
    ) -> None:
        if effect.presentation is not None:
            self._record_slash_command_result(
                command_name,
                effect.presentation.title,
                effect.presentation.body,
                severity=effect.presentation.severity,
                empty=effect.presentation.empty,
                action_hint=effect.presentation.action_hint,
            )

    def _apply_textual_execute_workspace_picker_effect(
        self,
        effect: ExecuteCommandEffect,
    ) -> None:
        if effect.workspace_picker_snapshot is not None:
            self._open_execute_workspace_picker(effect.workspace_picker_snapshot)

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
        action = self._build_textual_ask_command_action(args)
        if action.presentation is not None:
            self._record_ask_command_presentation(command_name, action.presentation)
            return
        self._apply_textual_ask_run(self._run_textual_ask_command(action))

    def _build_textual_ask_command_action(
        self,
        args: list[str],
    ) -> AskCommandAction:
        return ask_command_action(
            args,
            self.config.active_agents.keys(),
            current_route=self.current_route,
            lang=self.config.lang,
        )

    def _run_textual_ask_command(self, action: AskCommandAction) -> AskCommandRun:
        return run_ask_command(
            action,
            nexus=self.get_screen("nexus", NexusScreen),
            workflow_controller=self.workflow_controller,
            workspace_candidate=self.workspace_candidate,
            project_dir=self.config.project_dir,
        )

    def _record_ask_command_presentation(
        self,
        command_name: str,
        presentation: AskCommandPresentation,
    ) -> None:
        self._record_slash_command_result(
            command_name,
            presentation.title,
            presentation.body,
            severity=presentation.severity,
            empty=presentation.empty,
            action_hint=presentation.action_hint,
        )

    def _apply_textual_ask_run(self, run: AskCommandRun) -> None:
        effect = ask_command_run_effect(run)
        if effect.initial_prompt:
            self.initial_prompt = effect.initial_prompt
        if effect.remember_target_preflight:
            self._remember_confirmed_target_preflight(
                effect.target_workspace,
                effect.target_snapshot,
            )
        self._apply_workflow_outcome(run.outcome)
        if effect.switch_to_nexus:
            self.switch_to("nexus")
            return

        if effect.workspace_picker_snapshot is not None:
            self._open_execute_workspace_picker(effect.workspace_picker_snapshot)

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
        start_modal: bool = True,
        **snapshot_options: LocalCommandSnapshotOptionValue,
    ) -> None:
        """Record a local slash command result in the central Textual view."""
        self._record_local_command_snapshot(
            local_command_snapshot(command, title, body, **snapshot_options),
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
        self._apply_local_command_result_effect(
            self._build_local_command_result_effect(
                result,
                start_modal=start_modal,
                notify=notify,
            )
        )

    def _build_local_command_result_effect(
        self,
        result: LocalCommandSnapshot,
        *,
        start_modal: bool,
        notify: bool,
    ) -> LocalCommandResultEffect:
        return local_command_result_effect(
            result,
            self._current_textual_snapshot(),
            self._local_command_results,
            current_route=self.current_route,
            start_modal=start_modal,
            notify=notify,
            lang=self.config.lang,
        )

    def _apply_local_command_result_effect(
        self,
        effect: LocalCommandResultEffect,
    ) -> None:
        self._local_command_results = effect.local_command_results
        self.active_snapshot = effect.snapshot
        if effect.show_modal and effect.modal_result is not None:
            self.push_screen(LocalCommandModal(effect.modal_result, lang=self.config.lang))
        else:
            self._apply_workflow_outcome(TextualWorkflowOutcome(effect.snapshot))
        if effect.notification is not None:
            self.notify(
                effect.notification.message,
                title=effect.notification.title,
                severity=effect.notification.severity,
            )

    def _show_textual_status(
        self,
        command: str,
        snapshot: WorkflowNexusSnapshot,
    ) -> None:
        """Show status in the surface appropriate for the current Textual route."""
        effect = status_command_effect(
            command,
            snapshot,
            self._local_command_results,
            current_route=self.current_route,
            extra_table_rows=self._status_provider_notice_rows(),
            lang=self.config.lang,
        )
        self._apply_textual_status_effect(effect)

    def _status_provider_notice_rows(self) -> tuple[tuple[str, str], ...]:
        selected_agents: tuple[str, ...] | None = None
        selector = self._active_agent_selector()
        if selector is not None:
            selected_agents = selector.selected_agents()
        notices = (
            provider_execution_review_policy_label(
                self.config.agents,
                selected_agents=selected_agents,
                lang=self.config.lang,
            ),
            provider_cli_setup_label(
                self.config.agents,
                selected_agents=selected_agents,
                lang=self.config.lang,
            ),
        )
        rows: list[tuple[str, str]] = []
        for notice in notices:
            if not notice:
                continue
            item, _, value = notice.partition(": ")
            rows.append((item, value or notice))
        return tuple(rows)

    def _apply_textual_status_effect(self, effect: LocalCommandResultEffect) -> None:
        self._local_command_results = effect.local_command_results
        self.active_snapshot = effect.snapshot
        if effect.show_modal and effect.modal_result is not None:
            self.push_screen(
                StatusCommandModal(effect.modal_result, lang=self.config.lang)
            )
            return
        self._apply_workflow_outcome(TextualWorkflowOutcome(effect.snapshot))

    def _open_model_settings_modal(self) -> None:
        """Open the model settings modal for the active prompt selector."""
        selector = self._active_agent_selector()
        if selector is not None:
            self._refresh_provider_models(use_cache=False)
        request = model_settings_modal_request(
            selector,
            self._agent_model_choices,
            lang=self.config.lang,
        )
        self._apply_model_settings_modal_request(request)

    def _apply_model_settings_modal_request(
        self,
        request: ModelSettingsModalRequest,
    ) -> None:
        if request.notification is not None:
            self._notify_model_settings_request(request.notification)
            return
        self._push_model_settings_modal(request)

    def _notify_model_settings_request(
        self,
        notification: ModelSettingsNotification,
    ) -> None:
        self.notify(
            notification.message,
            title=notification.title,
            severity=notification.severity,
        )

    def _push_model_settings_modal(
        self,
        request: ModelSettingsModalRequest,
    ) -> None:
        self.push_screen(
            ModelSettingsModal(
                self.config.agents,
                request.choices_by_agent or {},
                request.selected_models or {},
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
        self._apply_textual_context_presentation(presentation, snapshot)

    def _apply_textual_context_presentation(
        self,
        presentation: ContextCommandPresentation,
        snapshot: WorkflowNexusSnapshot,
    ) -> None:
        effect = context_command_effect(
            presentation,
            snapshot,
            self._local_command_results,
        )
        self._apply_textual_context_effect(effect)

    def _apply_textual_context_effect(self, effect: ContextCommandEffect) -> None:
        if effect.action == "notify":
            self._notify_textual_context_effect(effect)
            return
        if effect.action == "record":
            self._record_textual_context_effect(effect)
            return
        self._apply_textual_context_snapshot_effect(effect)

    def _notify_textual_context_effect(self, effect: ContextCommandEffect) -> None:
        self.notify(
            effect.body,
            title=effect.title,
            severity=effect.severity,
        )

    def _record_textual_context_effect(self, effect: ContextCommandEffect) -> None:
        self._record_slash_command_result(
            effect.command,
            effect.title,
            effect.body,
            severity=effect.severity,
        )

    def _apply_textual_context_snapshot_effect(
        self,
        effect: ContextCommandEffect,
    ) -> None:
        if effect.local_command_results is None or effect.snapshot is None:
            return
        self._local_command_results = effect.local_command_results
        self.active_snapshot = effect.snapshot
        if effect.action == "modal" and effect.result is not None:
            self.push_screen(ContextCommandModal(effect.result, lang=self.config.lang))
            return
        if effect.action == "workflow_outcome":
            self._apply_workflow_outcome(TextualWorkflowOutcome(effect.snapshot))

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
        presentation = report_command_presentation(
            args,
            snapshot,
            self._export_report_markdown,
            lang=self.config.lang,
        )
        self._record_report_command_presentation(presentation)
        if presentation.switch_to_report:
            self.switch_to("report")

    def _record_report_command_presentation(
        self,
        presentation: ReportCommandPresentation,
    ) -> None:
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

    def _handle_textual_rounds_command(
        self,
        command_name: str,
        args: list[str],
    ) -> None:
        self._record_slash_command_presentation(
            command_name,
            rounds_command_presentation(self.config, args, lang=self.config.lang),
        )

    def _handle_textual_agent_command(
        self,
        command_name: str,
        args: list[str],
    ) -> None:
        before = {
            name: bool(spec.enabled)
            for name, spec in self.config.agents.items()
        }
        self._record_slash_command_presentation(
            command_name,
            agent_command_presentation(self.config.agents, args, lang=self.config.lang),
        )
        after = {
            name: bool(spec.enabled)
            for name, spec in self.config.agents.items()
        }
        changed = {
            name
            for name, was_enabled in before.items()
            if after.get(name) != was_enabled
        }
        if not changed:
            return
        self._sync_agent_enabled_surfaces()
        self._refresh_agent_enabled_snapshot()
        if any(after.get(name) for name in changed):
            self._refresh_provider_models(use_cache=True)

    def _handle_textual_caveman_command(
        self,
        command_name: str,
        args: list[str],
    ) -> None:
        self._record_slash_command_presentation(
            command_name,
            caveman_command_presentation(self.config, args, lang=self.config.lang),
        )

    def _handle_textual_target_command(self, args: list[str]) -> None:
        target = getattr(self.workflow_controller, "workflow", None)
        current = target.session.target_workspace if target is not None else None
        action = target_command_action(
            args,
            current=current,
            project_dir=self.config.project_dir,
            lang=self.config.lang,
        )
        self._apply_textual_target_command_effect(target_command_effect(action))

    def _apply_textual_target_command_effect(
        self,
        effect: TargetCommandEffect,
    ) -> None:
        if effect.presentation is not None:
            self._record_target_command_presentation(effect.presentation)
            return
        if effect.action == "clear":
            self._clear_textual_target_workspace()
            return
        self._apply_textual_target_path_action(effect)

    def _clear_textual_target_workspace(self) -> None:
        outcome = self.workflow_controller.clear_target_workspace()
        self.confirmed_preflight = None
        self._apply_workflow_outcome(outcome)
        self._record_target_command_presentation(
            target_cleared_presentation(lang=self.config.lang)
        )

    def _apply_textual_target_path_action(
        self,
        effect: TargetCommandEffect,
    ) -> None:
        if effect.path is None:
            return
        if effect.action == "confirm":
            self._confirm_textual_target_workspace(effect.path)
            return
        self._set_textual_target_workspace(effect.path, control_repo_confirmed=False)

    def _record_target_command_presentation(
        self,
        presentation: TargetCommandPresentation,
    ) -> None:
        self._record_slash_command_result(
            "/target",
            presentation.title,
            presentation.body,
            severity=presentation.severity,
            empty=presentation.empty,
            action_hint=presentation.action_hint,
            table_columns=presentation.table_columns,
            table_rows=presentation.table_rows,
        )

    def _confirm_textual_target_workspace(self, path: Path) -> None:
        self._open_target_workspace_confirm_modal(
            path,
            lambda confirmed: self._on_target_workspace_confirmed(
                path,
                confirmed,
            ),
        )

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
        self._apply_textual_target_workspace_preparation(
            prepare_target_workspace(path),
            control_repo_confirmed=control_repo_confirmed,
        )

    def _apply_textual_target_workspace_preparation(
        self,
        prepared: TargetWorkspacePreparation,
        *,
        control_repo_confirmed: bool,
    ) -> None:
        if self._record_textual_target_prepare_result(prepared):
            return
        if prepared.resolved_path is None:
            return
        self._apply_textual_target_workspace(
            prepared.resolved_path,
            control_repo_confirmed=control_repo_confirmed,
        )

    def _record_textual_target_prepare_result(
        self,
        prepared: TargetWorkspacePreparation,
    ) -> bool:
        presentation = target_prepare_result_presentation(
            prepared,
            lang=self.config.lang,
        )
        if presentation:
            self._record_target_command_presentation(presentation)
            return True
        return False

    def _apply_textual_target_workspace(
        self,
        resolved: Path,
        *,
        control_repo_confirmed: bool,
    ) -> None:
        self._apply_textual_target_workspace_effect(
            self._build_textual_target_workspace_effect(
                resolved,
                control_repo_confirmed=control_repo_confirmed,
            )
        )

    def _build_textual_target_workspace_effect(
        self,
        resolved: Path,
        *,
        control_repo_confirmed: bool,
    ) -> TargetWorkspaceApplyEffect:
        return target_workspace_apply_effect(
            resolved,
            self._set_textual_target_workspace_outcome(
                resolved,
                control_repo_confirmed=control_repo_confirmed,
            ),
            self._current_textual_snapshot(),
            control_repo=self.config.project_dir,
            control_repo_confirmed=control_repo_confirmed,
            lang=self.config.lang,
        )

    def _set_textual_target_workspace_outcome(
        self,
        resolved: Path,
        *,
        control_repo_confirmed: bool,
    ) -> TextualWorkflowOutcome:
        return self.workflow_controller.set_target_workspace(
            resolved,
            control_repo_confirmed=control_repo_confirmed,
        )

    def _apply_textual_target_workspace_effect(
        self,
        effect: TargetWorkspaceApplyEffect,
    ) -> None:
        self._remember_confirmed_target_preflight(effect.resolved, effect.snapshot)
        if effect.apply_workflow_outcome:
            self._apply_workflow_outcome(effect.workflow_outcome)
        self._set_workspace_candidate(effect.resolved)
        self._record_target_command_presentation(effect.presentation)

    def _sync_nexus_workspace_candidate(self) -> None:
        if not self._screens_installed:
            return
        self.get_screen("nexus", NexusScreen).set_workspace_candidate(
            self.workspace_candidate,
        )

    def _safe_nexus_target_workspace(
        self,
        snapshot: WorkflowNexusSnapshot | None,
    ) -> Path | None:
        candidates: list[Path] = []
        snapshot_target = (snapshot.target_workspace or "").strip() if snapshot else ""
        if snapshot_target:
            candidates.append(Path(snapshot_target))
        if self.workspace_candidate is not None:
            candidates.append(self.workspace_candidate)
        for candidate in candidates:
            safe = safe_start_target_workspace(candidate, self.config.project_dir)
            if safe is not None:
                return safe
        return None

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
        action = resume_command_action(
            args,
            self.workflow_controller.list_resume_options(),
            lang=self.config.lang,
        )
        if action.presentation:
            self._record_resume_command_presentation(action.presentation)
        if action.kind == "picker":
            self.push_screen(
                ResumeWorkflowPicker(list(action.archives), lang=self.config.lang),
                self._on_resume_archive_selected,
            )
            return
        if action.kind == "resume":
            self._resume_textual_workflow(action.selector)

    def _record_resume_command_presentation(
        self,
        presentation: ResumeCommandPresentation,
    ) -> None:
        self._record_slash_command_result(
            "/resume",
            presentation.title,
            presentation.body,
            severity=presentation.severity,
            empty=presentation.empty,
            action_hint=presentation.action_hint,
            table_columns=presentation.table_columns,
            table_rows=presentation.table_rows,
            start_modal=presentation.start_modal,
        )

    def _on_resume_archive_selected(self, selector: str | None) -> None:
        if selector is None:
            self._record_resume_command_presentation(
                resume_cancelled_presentation(lang=self.config.lang)
            )
            return
        self._resume_textual_workflow(selector)

    def _resume_textual_workflow(self, selector: str) -> None:
        outcome = self.workflow_controller.resume_workflow(selector)
        outcome, message = self._apply_workflow_outcome_without_inline_message(outcome)
        effect = resume_workflow_effect(outcome, message, lang=self.config.lang)
        if effect.presentation:
            self._record_resume_command_presentation(effect.presentation)
        if effect.switch_to_nexus:
            self.switch_to("nexus")
            if effect.execution_recovery_snapshot is not None:
                self._present_execution_recovery(
                    "/resume",
                    effect.execution_recovery_snapshot,
                    effect.execution_recovery_message,
                )
            if effect.show_context:
                self._handle_textual_context_command("/context")

    def _handle_textual_answer_command(self, args: list[str]) -> None:
        run = run_answer_command(
            args,
            self.workflow_controller,
            lang=self.config.lang,
        )
        if run.presentation:
            self._record_answer_command_presentation(run.presentation)
            return
        self._apply_textual_answer_run(run)

    def _record_answer_command_presentation(
        self,
        presentation: AnswerCommandPresentation,
    ) -> None:
        self._record_slash_command_result(
            "/answer",
            presentation.title,
            presentation.body,
            severity=presentation.severity,
            empty=presentation.empty,
            action_hint=presentation.action_hint,
        )

    def _apply_textual_answer_run(self, run: AnswerCommandRun) -> None:
        if run.outcome is None:
            return
        outcome = run.outcome
        outcome, message = self._apply_workflow_outcome_without_inline_message(outcome)
        result_presentation = answer_message_command_presentation(
            message,
            lang=self.config.lang,
        )
        if result_presentation:
            self._record_answer_command_presentation(result_presentation)

    def _handle_textual_execute_retry_command(self, args: list[str]) -> None:
        selector, package_ids = parse_execute_retry_args(args)
        self.workflow_controller.preview_execution_retry(selector, package_ids)
        snapshot = self._refresh_textual_snapshot()
        effect = execution_retry_request_effect(
            snapshot,
            selector,
            tuple(package_ids),
            lang=self.config.lang,
        )
        self._apply_textual_execute_retry_command_effect(effect)

    def _apply_textual_execute_retry_command_effect(
        self,
        effect: ExecutionRetryRequestEffect,
    ) -> None:
        if not effect.show_retry_modal:
            presentation = effect.no_packages_presentation
            if presentation is None:
                return
            self._record_execute_retry_no_packages(presentation)
            return
        self._open_execution_retry_modal(effect)

    def _record_execute_retry_no_packages(
        self,
        presentation: ExecuteCommandPresentation,
    ) -> None:
        self._record_slash_command_result(
            "/execute-retry",
            presentation.title,
            presentation.body,
            severity=presentation.severity,
            empty=presentation.empty,
            action_hint=presentation.action_hint,
        )

    def _open_execution_retry_modal(
        self,
        effect: ExecutionRetryRequestEffect,
    ) -> None:
        self.push_screen(
            ExecutionRetryModal(
                effect.snapshot,
                selector=effect.selector,
                package_ids=effect.package_ids,
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
        self._apply_execute_retry_selection_outcome(selection, outcome)

    def _apply_execute_retry_selection_outcome(
        self,
        selection: ExecutionRetrySelection,
        outcome: TextualWorkflowOutcome,
    ) -> None:
        if outcome.target_workspace_required:
            self._apply_execute_retry_target_workspace_required(selection, outcome)
            return
        self._apply_workflow_outcome(outcome)
        self._apply_execute_retry_execution_requested(outcome)

    def _apply_execute_retry_target_workspace_required(
        self,
        selection: ExecutionRetrySelection,
        outcome: TextualWorkflowOutcome,
    ) -> None:
        self._pending_execute_retry = selection
        self._apply_workflow_outcome(outcome)
        self._open_execute_workspace_picker(outcome.snapshot)

    def _apply_execute_retry_execution_requested(
        self,
        outcome: TextualWorkflowOutcome,
    ) -> None:
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
        self._prepare_route_switch(route)
        self.current_route = route
        self.switch_screen(route)
        self._schedule_route_refresh_after_switch(route)

    def _prepare_route_switch(self, route: WorkbenchRoute) -> None:
        if not self._screens_installed:
            return
        if route == "report":
            self._prepare_report_route()
        if route == "execution":
            self._prepare_execution_route()

    def _prepare_report_route(self) -> None:
        report = self.get_screen("report", ReportScreen)
        prepare_report_route(
            report,
            self.active_snapshot or self.snapshot_adapter.load_snapshot(),
            state_dir=self.config.effective_state_dir,
            event_limit=WORKFLOW_EVENT_DISPLAY_LIMIT,
            structured_snapshot=self.active_snapshot,
        )

    def _prepare_execution_route(self) -> None:
        apply_current_route_snapshot(
            self,
            "execution",
            self.active_snapshot
            or self.workflow_controller.snapshot()
            or self.snapshot_adapter.load_snapshot(),
            confirmed_preflight=self.confirmed_preflight,
            sync_nexus_workspace_candidate=self._sync_nexus_workspace_candidate,
            require_execution_preflight=False,
        )

    def _schedule_route_refresh_after_switch(self, route: WorkbenchRoute) -> None:
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
        filepath = export_report_markdown(
            snapshot,
            state_dir=self.config.effective_state_dir,
            lang=self.config.lang,
        )
        effect = report_export_effect(filepath, lang=self.config.lang)
        self._apply_report_export_effect(effect)
        return effect.path

    def _apply_report_export_effect(self, effect: ReportExportEffect) -> None:
        if effect.show_export_path and self._screens_installed and effect.path is not None:
            self.get_screen("report", ReportScreen).show_export_path(effect.path)
        notification = effect.notification
        notify_kwargs = {"title": notification.title}
        if notification.severity:
            notify_kwargs["severity"] = notification.severity
        self.notify(notification.message, **notify_kwargs)


def run_textual_app(config: TrinityConfig) -> None:
    """Run the Textual workbench."""
    TrinityTextualApp(config).run()
