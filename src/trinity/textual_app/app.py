"""Textual application shell for Trinity."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Literal

from textual.app import App
from textual.binding import Binding

from trinity import __version__
from trinity.config import TrinityConfig
from trinity.i18n import VALID_CAVEMAN_INTENSITIES
from trinity.slash_commands import (
    SESSION_ONLY_SETTING_NOTICE,
    TRINITY_COMMANDS,
    parse_slash_command,
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
from trinity.textual_app.settings import UISettingsStore
from trinity.textual_app.snapshot import (
    LocalCommandSnapshot,
    NexusSnapshotAdapter,
    WorkflowNexusSnapshot,
)
from trinity.textual_app.i18n import localize_bindings
from trinity.textual_app.workflow_controller import (
    TextualWorkflowController,
    TextualWorkflowOutcome,
)
from trinity.textual_app.widgets.context_modal import ContextCommandModal
from trinity.textual_app.widgets.provider_inspector import ProviderInspector
from trinity.textual_app.widgets.resume_picker import ResumeWorkflowPicker
from trinity.textual_app.widgets.status_modal import StatusCommandModal
from trinity.textual_app.widgets.workspace_picker import (
    WorkspacePicker,
    WorkspacePreflight,
    default_workspace_tree_root,
)
from trinity.tui.kitty_compat import install_textual_parser_patch

WorkbenchRoute = Literal["start", "nexus", "execution", "settings", "report"]
NO_CURRENT_CONTEXT_MESSAGE = (
    "No current session context. Start a prompt or resume a workflow first."
)


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
        overflow-y: auto;
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
        height: auto;
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

    def __init__(
        self,
        config: TrinityConfig,
        workflow_controller: TextualWorkflowController | None = None,
    ) -> None:
        install_textual_parser_patch()
        super().__init__()
        localize_bindings(self._bindings, config.lang, self.LOCALIZED_BINDINGS)
        self.config = config
        self.current_route: WorkbenchRoute = "start"
        self.initial_prompt: str | None = None
        self.workspace_candidate: Path | None = None
        self.snapshot_adapter = NexusSnapshotAdapter(config)
        self.active_snapshot: WorkflowNexusSnapshot | None = None
        self.settings_store = UISettingsStore(config.effective_state_dir)
        self.confirmed_preflight: WorkspacePreflight | None = None
        self.workflow_controller = workflow_controller or TextualWorkflowController(config)
        self._screens_installed = False
        self._workflow_polling_started = False
        self._local_command_results: list[LocalCommandSnapshot] = []

    def on_mount(self) -> None:
        self._install_workbench_screens()
        self.current_route = "start"
        self.push_screen("start")

    def _install_workbench_screens(self) -> None:
        if self._screens_installed:
            return

        self.install_screen(
            StartScreen(self.workspace_candidate, lang=self.config.lang),
            "start",
        )
        self.install_screen(NexusScreen(self.config), "nexus")
        self.install_screen(
            SettingsScreen(self.settings_store, lang=self.config.lang),
            "settings",
        )
        self.install_screen(ExecutionMatrixScreen(), "execution")
        self.install_screen(ReportScreen(), "report")

        self._screens_installed = True

    def on_start_screen_submitted(self, event: StartScreen.Submitted) -> None:
        event.stop()
        self.initial_prompt = event.prompt
        self.workspace_candidate = event.workspace_candidate
        nexus = self.get_screen("nexus", NexusScreen)
        nexus.set_initial_prompt(event.prompt)
        outcome = self.workflow_controller.start_prompt(event.prompt)
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
        )

    def on_nexus_screen_follow_up_submitted(
        self,
        event: NexusScreen.FollowUpSubmitted,
    ) -> None:
        event.stop()
        outcome = self.workflow_controller.submit_follow_up(event.text)
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
        if outcome.target_workspace_required:
            self._open_execute_workspace_picker(outcome.snapshot)

    def _open_execute_workspace_picker(self, snapshot: WorkflowNexusSnapshot) -> None:
        self._open_workspace_picker(snapshot, self._on_workspace_preflight)

    def _open_workspace_picker(
        self,
        snapshot: WorkflowNexusSnapshot,
        callback,
    ) -> None:
        self.push_screen(
            WorkspacePicker(
                candidate=self.workspace_candidate,
                lang=self.config.lang,
                snapshot=snapshot,
                cwd=self.config.project_dir,
                tree_root=default_workspace_tree_root(self.config.project_dir),
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

    def _on_workspace_preflight(self, preflight: WorkspacePreflight | None) -> None:
        if preflight is None:
            return
        self.confirmed_preflight = preflight
        self.workflow_controller.set_target_workspace(preflight.path)
        outcome = self.workflow_controller.request_execution()
        self._apply_workflow_outcome(outcome)
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
        elif getattr(self.workflow_controller, "is_running", False):
            self._advance_activity_frame()

    def _apply_workflow_outcome(self, outcome: TextualWorkflowOutcome) -> None:
        snapshot = self._with_local_command_results(outcome.snapshot)
        self.active_snapshot = snapshot
        if self._screens_installed:
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
            self._record_slash_command_result(
                parsed.token,
                "Unknown Command",
                f"`{parsed.token}` is not a Trinity slash command.",
                severity="warning",
            )
            return

        command = parsed.command_id
        args = list(parsed.args)

        if command in {"quit", "exit", "q"}:
            self.exit()
            return
        if command == "help":
            self._record_slash_command_result(
                parsed.spec.name,
                "Trinity Commands",
                "\n".join(f"- `{name}`" for name in TRINITY_COMMANDS),
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
            self._record_slash_command_result(
                parsed.spec.name,
                "Questions",
                self._questions_select_markdown(snapshot)
                if select_requested
                else self._questions_markdown(snapshot),
            )
            return
        if command == "decisions":
            snapshot = self._refresh_textual_snapshot()
            body = "\n".join(f"- {item}" for item in snapshot.decisions)
            self._record_slash_command_result(
                parsed.spec.name,
                "Decisions",
                body or "No workflow decisions recorded.",
            )
            return
        if command == "packages":
            snapshot = self._refresh_textual_snapshot()
            body = "\n".join(f"- {item}" for item in snapshot.work_packages)
            self._record_slash_command_result(
                parsed.spec.name,
                "Packages",
                body or "No workflow work packages generated.",
            )
            return
        if command == "subtasks":
            self._record_slash_command_result(
                parsed.spec.name,
                "Subtasks",
                "Subtask details are available in workflow reports when recorded.",
            )
            return
        if command == "context":
            self._handle_textual_context_command(parsed.spec.name)
            return
        if command == "history":
            self.notify(
                "Textual session history is shown in the central agent timeline.",
                title="History",
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
            self.notify(
                "Textual workflows are persisted automatically. Use /report save for Markdown export.",
                title="Save",
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
        if command == "execute":
            outcome = self.workflow_controller.request_execution(" ".join(args))
            self._apply_workflow_outcome(outcome)
            if outcome.target_workspace_required:
                self._open_execute_workspace_picker(outcome.snapshot)
            return

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
        table_columns: tuple[str, ...] = (),
        table_rows: tuple[tuple[str, ...], ...] = (),
    ) -> None:
        """Record a local slash command result in the central Textual view."""
        result = self._local_command_snapshot(
            command,
            title,
            body,
            severity=severity,
            table_columns=table_columns,
            table_rows=table_rows,
        )
        self._replace_local_command_result(result)
        snapshot = (
            self.workflow_controller.snapshot()
            or self.snapshot_adapter.load_snapshot()
        )
        self._apply_workflow_outcome(TextualWorkflowOutcome(snapshot))
        notify_severity = "warning" if severity in {"warning", "error"} else "information"
        self.notify(title, title="Slash Command", severity=notify_severity)

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

    def _local_command_snapshot(
        self,
        command: str,
        title: str,
        body: str,
        *,
        severity: str = "info",
        table_columns: tuple[str, ...] = (),
        table_rows: tuple[tuple[str, ...], ...] = (),
    ) -> LocalCommandSnapshot:
        """Build a local slash command result snapshot."""
        return LocalCommandSnapshot(
            command=command,
            title=title,
            body=body.strip() or "(no output)",
            severity=severity,
            table_columns=table_columns,
            table_rows=table_rows,
        )

    def _replace_local_command_result(
        self,
        result: LocalCommandSnapshot,
    ) -> None:
        """Keep only the latest result for each local slash command."""
        self._local_command_results = [
            item
            for item in self._local_command_results
            if item.command != result.command
        ]
        self._local_command_results.append(result)

    @staticmethod
    def _snapshot_status_markdown(snapshot: WorkflowNexusSnapshot) -> str:
        state = snapshot.state or "idle"
        goal = snapshot.goal or "(none)"
        lines = [
            f"- Workflow: `{snapshot.session_id or '(new)'}`",
            f"- State: `{state}`",
            f"- Round: `{snapshot.round_num}`",
            f"- Goal: {goal}",
            "",
            "| Provider | Enabled | Status | Readiness |",
            "| :--- | :--- | :--- | :--- |",
        ]
        if snapshot.providers:
            lines.extend(
                (
                    f"| {provider.name} | {'yes' if provider.enabled else 'no'} "
                    f"| {provider.status} | "
                    f"{TrinityTextualApp._readiness_label(provider.readiness)} |"
                )
                for provider in snapshot.providers
            )
        else:
            lines.append("| - | - | - | - |")
        return "\n".join(lines)

    @staticmethod
    def _snapshot_status_rows(
        snapshot: WorkflowNexusSnapshot,
    ) -> tuple[tuple[str, str], ...]:
        rows = [
            ("Workflow", snapshot.session_id or "(new)"),
            ("State", snapshot.state or "idle"),
            ("Round", str(snapshot.round_num)),
            ("Goal", snapshot.goal or "(none)"),
        ]
        for provider in snapshot.providers:
            rows.append(
                (
                    f"Provider: {provider.name}",
                    (
                        f"{provider.status}; enabled="
                        f"{'yes' if provider.enabled else 'no'}; "
                        f"readiness={TrinityTextualApp._readiness_label(provider.readiness)}"
                    ),
                )
            )
        return tuple(rows)

    @staticmethod
    def _readiness_label(readiness: str) -> str:
        if readiness == "unknown":
            return "not checked"
        return readiness

    @staticmethod
    def _snapshot_workflow_markdown(snapshot: WorkflowNexusSnapshot) -> str:
        state = snapshot.state or "idle"
        goal = snapshot.goal or "(none)"
        return "\n".join(
            [
                f"- ID: `{snapshot.session_id or '(new)'}`",
                f"- State: `{state}`",
                f"- Goal: {goal}",
                f"- Round: `{snapshot.round_num}`",
                f"- Pending questions: `{len(snapshot.questions)}`",
                f"- Decisions: `{len(snapshot.decisions)}`",
                f"- Work packages: `{len(snapshot.work_packages)}`",
                f"- Local policy repairs: `{len(snapshot.work_package_repairs)}`",
                f"- Execution log entries: `{len(snapshot.execution_log)}`",
            ]
        )

    @staticmethod
    def _snapshot_workflow_rows(
        snapshot: WorkflowNexusSnapshot,
    ) -> tuple[tuple[str, str], ...]:
        return (
            ("ID", snapshot.session_id or "(new)"),
            ("State", snapshot.state or "idle"),
            ("Goal", snapshot.goal or "(none)"),
            ("Round", str(snapshot.round_num)),
            ("Pending questions", str(len(snapshot.questions))),
            ("Decisions", str(len(snapshot.decisions))),
            ("Work packages", str(len(snapshot.work_packages))),
            ("Local policy repairs", str(len(snapshot.work_package_repairs))),
            ("Execution log entries", str(len(snapshot.execution_log))),
        )

    @staticmethod
    def _snapshot_has_current_context(snapshot: WorkflowNexusSnapshot) -> bool:
        return bool(
            snapshot.session_id
            or snapshot.goal
            or snapshot.round_num
            or snapshot.synthesis.summary
            or snapshot.synthesis.consensus_progress
            or snapshot.questions
            or snapshot.decisions
            or snapshot.central_work_packages
            or snapshot.work_packages
            or snapshot.work_package_repairs
            or snapshot.execution_log
        )

    @staticmethod
    def _snapshot_context_markdown(snapshot: WorkflowNexusSnapshot) -> str:
        if not TrinityTextualApp._snapshot_has_current_context(snapshot):
            return NO_CURRENT_CONTEXT_MESSAGE

        lines = [
            f"- Workflow: `{snapshot.session_id or '(new)'}`",
            f"- State: `{snapshot.state or 'idle'}`",
            f"- Goal: {snapshot.goal or '(none)'}",
            f"- Round: `{snapshot.round_num}`",
        ]
        if snapshot.synthesis.consensus_progress:
            lines.append(
                f"- Synthesis: `{snapshot.synthesis.consensus_progress}`"
            )
        if snapshot.synthesis.summary:
            lines.extend(["", "### Synthesis", snapshot.synthesis.summary])
        if snapshot.questions:
            lines.extend(["", "### Questions"])
            for question in snapshot.questions:
                status = question.status or "open"
                lines.append(f"- **{question.id}** [{status}] {question.question}")
                if question.answer:
                    lines.append(f"  - Answer: {question.answer}")
        if snapshot.decisions:
            lines.extend(["", "### Decisions"])
            lines.extend(f"- {item}" for item in snapshot.decisions)
        packages = snapshot.work_packages or snapshot.central_work_packages
        if packages:
            lines.extend(["", "### Work Packages"])
            lines.extend(f"- {item}" for item in packages)
        if snapshot.work_package_repairs:
            lines.extend(["", "### Local Policy Repairs"])
            lines.extend(f"- {item}" for item in snapshot.work_package_repairs)
        if snapshot.execution_log:
            lines.extend(["", "### Recent Execution Log"])
            lines.extend(f"- {item}" for item in snapshot.execution_log[-8:])
        return "\n".join(lines)

    @staticmethod
    def _questions_markdown(snapshot: WorkflowNexusSnapshot) -> str:
        if not snapshot.questions:
            return "No pending workflow questions."
        lines: list[str] = []
        for index, question in enumerate(snapshot.questions, start=1):
            lines.append(f"{index}. **{question.id}** [{question.status}] {question.question}")
            if question.answer:
                lines.append(f"   - Answer: {question.answer}")
            if question.recommended_option:
                lines.append(f"   - Recommended: {question.recommended_option}")
            for option_index, option in enumerate(question.options, start=1):
                lines.append(f"   - {option_index}. {option}")
        lines.append("")
        lines.append("Use central panel buttons or `/answer <id|index|next> <answer>`.")
        return "\n".join(lines)

    @staticmethod
    def _questions_select_markdown(snapshot: WorkflowNexusSnapshot) -> str:
        if not snapshot.questions:
            return "No pending workflow questions to select."
        question = snapshot.questions[0]
        lines = [
            f"Selected question: **{question.id}**",
            question.question,
        ]
        if question.options:
            lines.append("")
            lines.append(
                "Use the option buttons in the central panel, "
                "or run `/answer <option-number>`."
            )
            for index, option in enumerate(question.options, start=1):
                lines.append(f"- {index}. {option}")
        else:
            lines.append("")
            lines.append("This question has no predefined options.")
            lines.append("Use `/answer <id|index|next> <answer>`.")
        return "\n".join(lines)

    def _handle_textual_context_command(self, command: str) -> None:
        """Show the current session context without reading stale shared.md state."""
        snapshot = self._current_textual_snapshot()
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

    def _handle_textual_report_command(self, args: list[str]) -> None:
        snapshot = self._refresh_textual_snapshot()
        if args and args[0].lower() in {"save", "s"}:
            self._export_report_markdown(snapshot)
            return
        if not snapshot_has_report_data(snapshot):
            self.notify(
                "No workflow data available for a report.",
                title="Report",
                severity="warning",
            )
            return
        self.switch_to("report")

    @staticmethod
    def _session_setting_body(message: str) -> str:
        return f"{message}\n\n{SESSION_ONLY_SETTING_NOTICE}"

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
            )
            return
        if rounds < 1 or rounds > 20:
            self._record_slash_command_result(
                command_name,
                "Rounds",
                "Rounds must be between 1 and 20.",
                severity="warning",
            )
            return
        self.config.max_deliberation_rounds = rounds
        self._record_slash_command_result(
            command_name,
            "Rounds",
            self._session_setting_body(
                f"Max rounds set to `{rounds}` for this session only."
            ),
        )

    def _handle_textual_agent_command(
        self,
        command_name: str,
        args: list[str],
    ) -> None:
        if len(args) < 2:
            self._record_slash_command_result(
                command_name,
                "Agent",
                "Usage: `/agent <name> on|off`",
                severity="warning",
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
            )
            return
        if action not in {"on", "off"}:
            self._record_slash_command_result(
                command_name,
                "Agent",
                "Usage: `/agent <name> on|off`",
                severity="warning",
            )
            return
        spec.enabled = action == "on"
        status = "enabled" if spec.enabled else "disabled"
        self._record_slash_command_result(
            command_name,
            "Agent",
            self._session_setting_body(
                f"Agent `{name}` {status} for this session only."
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
                "Caveman",
                self._session_setting_body(
                    f"Caveman: `{mode}` (`{self.config.caveman_intensity}`)."
                ),
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
        )

    def _handle_textual_target_command(self, args: list[str]) -> None:
        if not args:
            target = getattr(self.workflow_controller, "workflow", None)
            current = None
            if target is not None:
                current = target.session.target_workspace
            self.notify(f"Current target: {current or '(not set)'}", title="Target")
            return
        action = args[0].lower()
        if action in {"clear", "reset", "none"}:
            outcome = self.workflow_controller.clear_target_workspace()
            self._apply_workflow_outcome(outcome)
            self.notify("Target workspace cleared.", title="Target")
            return
        path = Path(" ".join(args)).expanduser()
        if not path.is_absolute():
            path = self.config.project_dir / path
        path.mkdir(parents=True, exist_ok=True)
        outcome = self.workflow_controller.set_target_workspace(path)
        if isinstance(outcome, TextualWorkflowOutcome):
            self._apply_workflow_outcome(outcome)
        self.notify(f"Target workspace: {path.resolve()}", title="Target")

    def _handle_textual_resume_command(self, args: list[str]) -> None:
        if not args:
            archives = self.workflow_controller.list_resume_options()
            if not archives:
                self.notify("No saved workflow sessions to resume.", title="Resume")
                return
            self.push_screen(
                ResumeWorkflowPicker(archives, lang=self.config.lang),
                self._on_resume_archive_selected,
            )
            return
        selector = args[0].lower()
        self._resume_textual_workflow(selector)

    def _on_resume_archive_selected(self, selector: str | None) -> None:
        if selector is None:
            return
        self._resume_textual_workflow(selector)

    def _resume_textual_workflow(self, selector: str) -> None:
        outcome = self.workflow_controller.resume_workflow(selector)
        if outcome.message:
            severity = "warning" if outcome.message.startswith("No ") else "information"
            self.notify(outcome.message, title="Resume", severity=severity)
            outcome = replace(outcome, message="")
        self._apply_workflow_outcome(outcome)

    def _handle_textual_answer_command(self, args: list[str]) -> None:
        if not args:
            self.notify(
                "Usage: /answer <question-id|index|next> <answer>",
                title="Answer",
                severity="warning",
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
            self.notify(
                "Usage: /answer <question-id|index|next> <answer>",
                title="Answer",
                severity="warning",
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
        self._apply_workflow_outcome(outcome)

    def _advance_activity_frame(self) -> None:
        if self.current_route == "nexus" and self._screens_installed:
            nexus = self.get_screen("nexus", NexusScreen)
            nexus.advance_activity_frame()

    def switch_to(self, route: WorkbenchRoute) -> None:
        if route == "nexus" and self._screens_installed:
            nexus = self.get_screen("nexus", NexusScreen)
            nexus.apply_snapshot(
                self.active_snapshot
                or self.workflow_controller.snapshot()
                or self.snapshot_adapter.load_snapshot()
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
