from __future__ import annotations

from dataclasses import replace
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from textual import events
from textual.app import App
from textual.containers import VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Markdown,
    OptionList,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TextArea,
)

from trinity.config import TrinityConfig
from trinity.context.commands import engine_from_config
from trinity.context.shared import SharedContextEngine
from trinity.models import Provider
from trinity.project_intake import (
    build_project_intake,
    load_project_intake,
    write_project_intake,
)
from trinity.providers.model_discovery import ProviderModelChoice
from trinity.slash_commands import COMMAND_SPECS, SESSION_ONLY_SETTING_NOTICE
from trinity.textual_app import app as textual_app_module
from trinity.textual_app.app import (
    TrinityTextualApp,
    initial_workspace_candidate,
)
from trinity.textual_app.presenters import (
    agent_change_action_hint,
    agent_current_settings_markdown,
    agent_enabled_value,
    agent_rows,
    agent_status_markdown,
    agent_table_columns,
    agent_title,
    agent_unknown_markdown,
    agent_usage_markdown,
    answer_action_hint,
    answer_title,
    answer_usage_markdown,
    artifact_title,
    artifact_usage_markdown,
    ask_action_hint,
    ask_missing_model_markdown,
    ask_no_active_agents_markdown,
    ask_prompt_empty_markdown,
    ask_title,
    ask_unknown_agent_markdown,
    ask_usage_markdown,
    caveman_allowed_action_hint,
    caveman_change_action_hint,
    caveman_current_markdown,
    caveman_rows,
    caveman_set_markdown,
    caveman_title,
    caveman_usage_markdown,
    context_no_current_markdown,
    context_title,
    decisions_action_hint,
    decisions_markdown,
    decisions_rows,
    decisions_table_columns,
    execute_finish_planning_action_hint,
    execute_retry_no_packages_action_hint,
    execute_retry_no_packages_markdown,
    execute_retry_title,
    execute_title,
    execution_recovery_local_command_snapshot,
    execution_recovery_action_hint,
    execution_recovery_markdown,
    execution_recovery_rows,
    execution_recovery_table_columns,
    execution_recovery_title,
    history_action_hint,
    history_markdown,
    history_rows,
    history_table_columns,
    help_markdown,
    help_rows,
    help_table_columns,
    help_title,
    improve_action_hint,
    improve_rows,
    improve_table_columns,
    improve_title,
    local_command_snapshot,
    local_command_notification_severity,
    memory_cleanup_error_markdown,
    memory_title,
    model_settings_title,
    model_settings_unavailable_markdown,
    model_settings_updated_markdown,
    packages_action_hint,
    packages_markdown,
    packages_rows,
    packages_table_columns,
    questions_action_hint,
    questions_markdown,
    questions_rows,
    questions_select_markdown,
    questions_table_columns,
    report_export_complete_title,
    report_export_action_hint,
    report_no_export_data_markdown,
    report_no_open_data_markdown,
    report_open_action_hint,
    report_opened_markdown,
    report_saved_markdown,
    report_saved_notification,
    report_saved_rows,
    report_summary_rows,
    report_title,
    report_export_unavailable_title,
    review_action_hint,
    review_repair_action_hint,
    review_repair_blocked_ids,
    review_repair_details_markdown,
    review_repair_local_command_snapshot,
    review_repair_rows,
    review_repair_table_columns,
    review_repair_title,
    review_rows,
    review_table_columns,
    review_title,
    resume_archive_rows,
    resume_archive_table_columns,
    resume_archives_markdown,
    resume_cancel_action_hint,
    resume_cancelled_markdown,
    resume_no_saved_action_hint,
    resume_no_saved_markdown,
    resume_pick_action_hint,
    resume_result_rows,
    resume_result_table_columns,
    resume_title,
    rounds_change_action_hint,
    rounds_current_markdown,
    rounds_invalid_number_markdown,
    rounds_range_error_markdown,
    rounds_rows,
    rounds_set_markdown,
    rounds_title,
    rounds_usage_action_hint,
    snapshot_context_markdown,
    save_auto_persist_markdown,
    save_title,
    session_setting_body,
    snapshot_status_markdown,
    snapshot_status_rows,
    snapshot_workflow_markdown,
    snapshot_workflow_rows,
    slash_command_notification_title,
    status_table_columns,
    status_local_command_snapshot,
    status_title,
    subtasks_action_hint,
    subtasks_markdown,
    subtasks_rows,
    subtasks_table_columns,
    syntax_error_title,
    target_action_hint,
    target_cancelled_local_command_snapshot,
    target_cleared_markdown,
    target_control_repo_action_hint,
    target_current_markdown,
    target_not_directory_markdown,
    target_prepare_failed_markdown,
    target_preflight_cancelled_markdown,
    target_rows,
    target_selection_cancelled_markdown,
    target_title,
    target_workspace_markdown,
    unknown_command_markdown,
    unknown_command_rows,
    unknown_command_table_columns,
    unknown_command_title,
    workflow_outcome_message_markdown,
)
from trinity.textual_app.report_export import (
    snapshot_report_markdown,
    unique_report_path,
)
from trinity.textual_app.screens.execution_matrix import (
    ExecutionPackageRow,
    ExecutionMatrixScreen,
    _detail_button_label,
    _review_label,
)
from trinity.textual_app.screens.nexus import NexusScreen
from trinity.textual_app.screens.report import (
    ReportScreen,
    _field_label,
    _render_synthesis,
    _section_label,
)
from trinity.textual_app.screens.settings import SettingsScreen
from trinity.textual_app.screens.start import SacredGeometryAnimation, StartScreen
from trinity.textual_app.slash_palette import SlashCommandPaletteProvider
from trinity.textual_app.status_commands import status_command_result
from trinity.textual_app.settings import UISettings, UISettingsStore
from trinity.textual_app.snapshot import (
    AgentQualitySnapshot,
    PostReviewActionSnapshot,
    LocalCommandSnapshot,
    NexusSnapshotAdapter,
    ProviderSnapshot,
    QuestionSnapshot,
    ReviewSnapshot,
    SubtaskSnapshot,
    SynthesisSnapshot,
    ExecutionRecoverySnapshot,
    WorkflowNexusSnapshot,
    WorkPackageSnapshot,
)
from trinity.textual_app.workflow_controller import (
    TextualWorkflowArchiveOption,
    TextualWorkflowOutcome,
)
from trinity.tui.report import DeliberationReportBuilder
from trinity.textual_app.widgets.central_agent import CentralAgentView
from trinity.textual_app.widgets.agent_recipient_model_selector import (
    AgentToggle,
    AgentRecipientModelSelector,
)
from trinity.textual_app.widgets.composer import COMMAND_LIMIT, ComposerTextArea, PromptComposer
from trinity.textual_app.widgets.confirm_quit_modal import ConfirmQuitModal
from trinity.textual_app.widgets.context_modal import ContextCommandModal
from trinity.textual_app.widgets.execution_log_modal import (
    ExecutionLogModal,
    MAX_RENDERED_LOG_LINES,
)
from trinity.textual_app.widgets.execution_retry_modal import (
    ExecutionRetryModal,
    ExecutionRetrySelection,
    _retry_note,
)
from trinity.textual_app.widgets.execution_confirm_modal import ExecutionConfirmModal
from trinity.textual_app.widgets.inspector import WorkflowInspector
from trinity.textual_app.widgets.local_command_modal import LocalCommandModal
from trinity.textual_app.widgets.model_settings_modal import ModelSettingsModal
from trinity.textual_app.widgets.provider_inspector import (
    ProviderInspector,
    provider_inspector_label,
    provider_inspector_provider_output,
)
from trinity.textual_app.widgets.provider_panel import ProviderPanel
from trinity.textual_app.widgets.question_panel import QuestionPanel
from trinity.textual_app.widgets.resume_picker import ResumeWorkflowPicker
from trinity.textual_app.widgets.status_modal import StatusCommandModal
from trinity.textual_app.widgets.target_workspace_confirm_modal import (
    TargetWorkspaceConfirmModal,
)
from trinity.textual_app.widgets.work_package_detail_modal import WorkPackageDetailModal
from trinity.textual_app.widgets.workspace_picker import (
    WorkspacePicker,
    build_preflight,
)
from trinity.workflow import (
    ArchitectureComponent,
    Blueprint,
    OpenQuestion,
    RiskItem,
    WorkPackage,
    WorkflowPersistence,
    WorkflowSession,
    WorkflowState,
    WorkStatus,
)


class ScreenHarness(App[None]):
    def __init__(self, screen) -> None:
        super().__init__()
        self.target_screen = screen

    def on_mount(self) -> None:
        self.push_screen(self.target_screen)


class FakeWorkflowController:
    def __init__(self, snapshot: WorkflowNexusSnapshot | None = None) -> None:
        self.current_snapshot = snapshot or WorkflowNexusSnapshot()
        self.started_prompts: list[str] = []
        self.started_targets: list[tuple[str, ...]] = []
        self.started_models: list[dict[str, str]] = []
        self.follow_ups: list[str] = []
        self.follow_up_targets: list[tuple[str, ...]] = []
        self.follow_up_models: list[dict[str, str]] = []
        self.follow_up_workspaces: list[Path | None] = []
        self.answers: list[tuple[str, str, bool]] = []
        self.option_answers: list[tuple[str, str, bool]] = []
        self.answer_outcome: TextualWorkflowOutcome | None = None
        self.resumes: list[str] = []
        self.resume_options: list[TextualWorkflowArchiveOption] = []
        self.execution_outcome: TextualWorkflowOutcome | None = None
        self.execution_requests = 0
        self.execution_instructions: list[str] = []
        self.retry_previews: list[tuple[str, list[str]]] = []
        self.retry_confirms: list[tuple[str, list[str]]] = []
        self.retry_outcome: TextualWorkflowOutcome | None = None
        self.review_requests: list[tuple[str, ...]] = []
        self.review_outcome: TextualWorkflowOutcome | None = None
        self.improve_requests: list[tuple[str, ...]] = []
        self.improve_outcome: TextualWorkflowOutcome | None = None
        self.repair_actions: list[str] = []
        self.drain_outcome: TextualWorkflowOutcome | None = None
        self.target_workspace = None
        self.target_control_confirmed = False
        self.target_cleared = False

    def snapshot(self) -> WorkflowNexusSnapshot:
        return self.current_snapshot

    def start_prompt(
        self,
        prompt: str,
        *,
        target_workspace=None,
        control_repo_confirmed: bool = False,
        target_agents=(),
        agent_model_overrides=None,
    ) -> TextualWorkflowOutcome:
        self.started_prompts.append(prompt)
        self.started_targets.append(tuple(target_agents))
        self.started_models.append(dict(agent_model_overrides or {}))
        if target_workspace is not None:
            self.target_workspace = target_workspace
            self.target_control_confirmed = control_repo_confirmed
        self.current_snapshot = WorkflowNexusSnapshot(
            session_id="wf-fake",
            goal=prompt,
            state="deliberating",
            target_workspace=str(target_workspace or ""),
            providers=[
                ProviderSnapshot(
                    name="claude",
                    provider="claude-code",
                    enabled=True,
                    status="Running",
                )
            ],
        )
        return TextualWorkflowOutcome(self.current_snapshot, running=False)

    def submit_follow_up(
        self,
        text: str,
        *,
        target_agents=(),
        agent_model_overrides=None,
    ) -> TextualWorkflowOutcome:
        self.follow_ups.append(text)
        self.follow_up_targets.append(tuple(target_agents))
        self.follow_up_models.append(dict(agent_model_overrides or {}))
        self.follow_up_workspaces.append(self.target_workspace)
        self.current_snapshot = WorkflowNexusSnapshot(
            session_id="wf-fake",
            goal=self.current_snapshot.goal,
            state="deliberating",
            work_packages=[f"follow-up: {text}"],
            target_workspace=str(self.target_workspace or ""),
        )
        return TextualWorkflowOutcome(self.current_snapshot)

    def answer_question(
        self,
        question_id: str,
        answer: str,
        *,
        replace: bool = False,
    ) -> TextualWorkflowOutcome:
        self.answers.append((question_id, answer, replace))
        if self.answer_outcome is not None:
            return self.answer_outcome
        self.current_snapshot = WorkflowNexusSnapshot(
            session_id="wf-fake",
            goal=self.current_snapshot.goal,
            state="deliberating",
            decisions=[answer],
        )
        return TextualWorkflowOutcome(self.current_snapshot)

    def answer_question_option(
        self,
        option_index: str,
        *,
        question_selector: str = "next",
        replace: bool = False,
    ) -> TextualWorkflowOutcome:
        self.option_answers.append((option_index, question_selector, replace))
        if self.answer_outcome is not None:
            return self.answer_outcome
        self.current_snapshot = WorkflowNexusSnapshot(
            session_id="wf-fake",
            goal=self.current_snapshot.goal,
            state="deliberating",
            decisions=[f"option {option_index}"],
        )
        return TextualWorkflowOutcome(self.current_snapshot)

    def request_execution(self, instruction: str = "") -> TextualWorkflowOutcome:
        self.execution_requests += 1
        self.execution_instructions.append(instruction)
        if self.execution_outcome is not None:
            return self.execution_outcome
        return TextualWorkflowOutcome(
            self.current_snapshot,
            target_workspace_required=True,
        )

    def preview_execution_retry(self, selector: str = "all", package_ids=()):
        self.retry_previews.append((selector, list(package_ids)))
        return None

    def confirm_execution_retry(self, selector: str = "all", package_ids=()):
        self.retry_confirms.append((selector, list(package_ids)))
        if self.retry_outcome is not None:
            return self.retry_outcome
        return TextualWorkflowOutcome(
            self.current_snapshot,
            message=f"Retrying work packages: {', '.join(package_ids)}.",
            execution_requested=True,
        )

    def request_review(self, args=()):
        self.review_requests.append(tuple(args))
        if self.review_outcome is not None:
            return self.review_outcome
        return TextualWorkflowOutcome(
            self.current_snapshot,
            message=f"Review started: {' '.join(str(arg) for arg in args)}.",
            running=True,
        )

    def request_improvement(self, args=()):
        self.improve_requests.append(tuple(args))
        if self.improve_outcome is not None:
            return self.improve_outcome
        return TextualWorkflowOutcome(
            self.current_snapshot,
            message=f"Improvement requested: {' '.join(str(arg) for arg in args)}.",
            running=False,
        )

    def retry_blocked_review_repairs(self) -> TextualWorkflowOutcome:
        self.repair_actions.append("retry")
        package_ids = [
            package.id
            for package in self.current_snapshot.work_package_details
            if package.status == "blocked" and package.repair_blocked_reason
        ]
        return self.confirm_execution_retry("custom", package_ids)

    def accept_blocked_review_repairs(self) -> TextualWorkflowOutcome:
        self.repair_actions.append("accept")
        self.current_snapshot = WorkflowNexusSnapshot(
            session_id=self.current_snapshot.session_id,
            goal=self.current_snapshot.goal,
            state="reviewing",
            work_package_details=self.current_snapshot.work_package_details,
        )
        return TextualWorkflowOutcome(
            self.current_snapshot,
            message="Accepted blocked review repairs.",
        )

    def stop_blocked_review_repairs(self) -> TextualWorkflowOutcome:
        self.repair_actions.append("stop")
        self.current_snapshot = WorkflowNexusSnapshot(
            session_id=self.current_snapshot.session_id,
            goal=self.current_snapshot.goal,
            state="failed",
            work_package_details=self.current_snapshot.work_package_details,
        )
        return TextualWorkflowOutcome(
            self.current_snapshot,
            message="Stopped blocked review repairs.",
        )

    def set_target_workspace(self, path, *, control_repo_confirmed: bool = False):
        self.target_workspace = path
        self.target_control_confirmed = control_repo_confirmed
        self.current_snapshot = replace(
            self.current_snapshot,
            target_workspace=str(path),
        )
        return TextualWorkflowOutcome(self.current_snapshot)

    def clear_target_workspace(self) -> TextualWorkflowOutcome:
        self.target_cleared = True
        self.target_workspace = None
        self.current_snapshot = replace(self.current_snapshot, target_workspace="")
        return TextualWorkflowOutcome(self.current_snapshot)

    def list_resume_options(self) -> list[TextualWorkflowArchiveOption]:
        return list(self.resume_options)

    def resume_workflow(self, selector: str = "latest") -> TextualWorkflowOutcome:
        self.resumes.append(selector)
        self.current_snapshot = WorkflowNexusSnapshot(
            session_id=f"wf-resumed-{selector}",
            goal="resumed",
            state="blueprint_ready",
        )
        return TextualWorkflowOutcome(
            self.current_snapshot,
            message=f"Resumed workflow wf-resumed-{selector}.",
        )

    def new_session(self) -> TextualWorkflowOutcome:
        self.current_snapshot = WorkflowNexusSnapshot()
        return TextualWorkflowOutcome(self.current_snapshot)

    def drain_updates(self):
        outcome = self.drain_outcome
        self.drain_outcome = None
        return outcome


def _binding_description(bindings_map, key: str, action: str) -> str:
    for binding in bindings_map.key_to_bindings.get(key, []):
        if binding.action == action:
            return binding.description
    raise AssertionError(f"missing binding {key} -> {action}")


def _binding_tooltip(bindings_map, key: str, action: str) -> str:
    for binding in bindings_map.key_to_bindings.get(key, []):
        if binding.action == action:
            return binding.tooltip
    raise AssertionError(f"missing binding {key} -> {action}")


def _local_command(snapshot: WorkflowNexusSnapshot, command: str) -> LocalCommandSnapshot:
    for result in snapshot.local_commands:
        if result.command == command:
            return result
    raise AssertionError(f"missing local command result for {command}")


def _column_class(widget, expected: list[str]) -> str:
    for class_name in expected:
        if widget.has_class(class_name):
            return class_name
    raise AssertionError(f"missing expected column class on {widget!r}")


def _widget_tree_text(widget) -> str:
    parts = []
    for child in widget.query("*"):
        rendered = str(child.render())
        if "textual.renderables.blank" not in rendered:
            parts.append(rendered)
    return " ".join(parts)


def _review_repair_blocked_snapshot() -> WorkflowNexusSnapshot:
    return WorkflowNexusSnapshot(
        session_id="wf-repair",
        goal="repair loop",
        state="needs_user_decision",
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-002",
                title="Adapter repair",
                owner_agent="claude",
                status="blocked",
                repair_attempt_count=2,
                repair_max_attempts=3,
                repair_blocked_reason="duplicate_required_changes",
                review_status="changes_requested",
                review_required_changes=["Handle retry idempotently."],
            )
        ],
        work_package_repairs=[
            "WP-002: blocked after 2 repair attempts (duplicate_required_changes)"
        ],
    )


def test_execution_retry_note_summarizes_repair_attempts() -> None:
    retryable = WorkPackageSnapshot(
        id="WP-001",
        title="client",
        owner_agent="codex",
        status="blocked",
        retryable=True,
        repair_attempt_count=2,
        repair_max_attempts=3,
        repair_blocked_reason="duplicate_required_changes",
    )
    disabled = WorkPackageSnapshot(
        id="WP-002",
        title="docs",
        owner_agent="claude",
        status="done",
        retryable=False,
        retry_disabled_reason="already done",
        repair_attempt_count=1,
        repair_max_attempts=3,
    )

    assert _retry_note(retryable) == "repair 2/3: duplicate_required_changes"
    assert _retry_note(retryable, lang="ko") == "복구 2/3: duplicate_required_changes"
    assert _retry_note(disabled) == "already done"
    assert _retry_note(disabled, lang="ko") == "이미 완료됨"


def test_textual_app_localizes_command_palette_bindings_in_korean(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path, lang="ko"))

    assert _binding_description(app._bindings, "ctrl+q", "quit") == "종료"
    assert _binding_description(app._bindings, "ctrl+4", "go_report") == "리포트"
    assert _binding_description(app._bindings, "ctrl+p", "command_palette") == "팔레트"
    assert _binding_tooltip(app._bindings, "ctrl+p", "command_palette") == "명령 팔레트 열기"


@pytest.mark.asyncio
async def test_textual_command_palette_discovers_slash_command_registry(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(100, 30)):
        provider = SlashCommandPaletteProvider(app.screen)
        discovered = [hit.text async for hit in provider.discover()]

    expected = [name for spec in COMMAND_SPECS for name in spec.names]
    assert SlashCommandPaletteProvider in TrinityTextualApp.COMMANDS
    assert discovered == expected


@pytest.mark.asyncio
async def test_textual_command_palette_runs_slash_command_handler(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(100, 30)):
        handled: list[str] = []
        app._handle_textual_slash_command = handled.append  # type: ignore[method-assign]
        provider = SlashCommandPaletteProvider(app.screen)
        status_hit = [hit async for hit in provider.search("status")][0]

        status_hit.command()

    assert handled == ["/status"]


def test_status_modal_centers_and_uses_read_only_table() -> None:
    assert "align: center middle" in StatusCommandModal.DEFAULT_CSS
    result = LocalCommandSnapshot(
        command="/status",
        title="Status",
        body="status",
        table_columns=("Item", "Value"),
        table_rows=(("Workflow", "(new)"),),
    )

    text = StatusCommandModal(result).status_table_text()

    assert "Item" in text
    assert "Value" in text
    assert "Workflow" in text


def test_status_command_result_appends_provider_notice_rows() -> None:
    result = status_command_result(
        "/status",
        WorkflowNexusSnapshot(session_id="wf-status"),
        extra_table_rows=(("Provider policy", "1 active"),),
    )

    assert result.table_rows[-1] == ("Provider policy", "1 active")


def test_status_modal_uses_korean_chrome_labels() -> None:
    result = LocalCommandSnapshot(command="/status", title="Status", body="status")
    modal = StatusCommandModal(result, lang="ko")

    assert modal.label_text("title") == "상태"
    assert modal.label_text("body").startswith("현재 로컬 상태")
    assert modal.label_text("close") == "닫기"
    assert modal.status_table_text() == "(상태 행 없음)"


def test_context_modal_uses_korean_chrome_labels() -> None:
    result = LocalCommandSnapshot(command="/context", title="Context", body="context")
    modal = ContextCommandModal(result, lang="ko")

    assert modal.label_text("title") == "현재 세션 컨텍스트"
    assert modal.label_text("close") == "닫기"


def test_local_command_modal_uses_korean_close_label() -> None:
    result = LocalCommandSnapshot(command="/workflow", title="Workflow", body="body")
    modal = LocalCommandModal(result, lang="ko")

    assert modal.label_text("close") == "닫기"


def test_resume_picker_modal_centers() -> None:
    assert "align: center middle" in ResumeWorkflowPicker.DEFAULT_CSS


def test_status_reports_interrupted_execution() -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-interrupted",
        state="executing",
        execution_recovery=ExecutionRecoverySnapshot(
            run_id="exec-run-test",
            state="interrupted",
            target_workspace="/home/zaemi/workspace/hyper",
            running_packages=("WP-001",),
            retry_candidates=("WP-001", "WP-003"),
            done_packages=("WP-002",),
            last_event="work_package_started",
        ),
    )

    markdown = snapshot_status_markdown(snapshot)
    rows = snapshot_status_rows(snapshot)

    assert "### Execution Recovery" in markdown
    assert "Execution: `interrupted`" in markdown
    assert ("Execution", "interrupted") in rows
    assert ("Retry candidates", "WP-001, WP-003") in rows


def test_execution_recovery_local_command_snapshot_uses_recovery_presenter() -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-recovery",
        state="executing",
        execution_recovery=ExecutionRecoverySnapshot(
            run_id="exec-run-test",
            state="interrupted",
            target_workspace="/home/user/workspace/msu",
            running_packages=("WP-001",),
            retry_candidates=("WP-001", "WP-003"),
            done_packages=("WP-002",),
            last_event="work_package_started",
        ),
    )

    result = execution_recovery_local_command_snapshot(
        "/execute-retry",
        snapshot,
        "Previous execution was interrupted.",
        lang="ko",
    )

    assert result.command == "/execute-retry"
    assert result.title == "실행 복구"
    assert result.severity == "warning"
    assert "이전 실행이 중단되었습니다." in result.body
    assert "- 실행: `중단`" in result.body
    assert result.action_hint == (
        "`/execute-retry`, `/execute mark-interrupted`, "
        "`/execute abort` 중 하나를 실행하세요."
    )
    assert result.table_columns == ("항목", "값")
    assert ("재시도 후보", "WP-001, WP-003") in result.table_rows


def test_status_presenter_uses_korean_labels() -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-ko",
        goal="상태 확인",
        state="executing",
        providers=[
            ProviderSnapshot(
                name="claude",
                provider="claude-code",
                enabled=True,
                status="Queued",
                readiness="unknown",
            )
        ],
        execution_recovery=ExecutionRecoverySnapshot(
            run_id="exec-run-test",
            state="interrupted",
            target_workspace="/home/user/workspace/msu",
            running_packages=("WP-001",),
            retry_candidates=("WP-001", "WP-003"),
            done_packages=("WP-002",),
            last_event="work_package_started",
        ),
    )

    markdown = snapshot_status_markdown(snapshot, lang="ko")
    rows = snapshot_status_rows(snapshot, lang="ko")

    assert status_title(lang="ko") == "상태"
    assert status_table_columns(lang="ko") == ("항목", "값")
    assert "- 워크플로우: `wf-ko`" in markdown
    assert "| 프로바이더 | 활성화 | 상태 | 준비 상태 |" in markdown
    assert "| claude | 예 | 대기 | 미확인 |" in markdown
    assert "### 실행 복구" in markdown
    assert "실행: `중단`" in markdown
    assert ("워크플로우", "wf-ko") in rows
    assert ("프로바이더: claude", "대기; 활성화=예; 준비 상태=미확인") in rows
    assert ("재시도 후보", "WP-001, WP-003") in rows


def test_status_local_command_snapshot_uses_status_presenter() -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-status",
        goal="상태 확인",
        state="executing",
    )

    result = status_local_command_snapshot("/status", snapshot, lang="ko")

    assert result.command == "/status"
    assert result.title == "상태"
    assert "- 워크플로우: `wf-status`" in result.body
    assert result.table_columns == ("항목", "값")
    assert ("상태", "실행 중") in result.table_rows


def test_status_presenter_uses_korean_placeholder_values() -> None:
    snapshot = WorkflowNexusSnapshot(
        execution_recovery=ExecutionRecoverySnapshot(),
    )

    markdown = snapshot_status_markdown(snapshot, lang="ko")
    rows = snapshot_status_rows(snapshot, lang="ko")

    assert "- 워크플로우: `(새 워크플로우)`" in markdown
    assert "- 목표: (없음)" in markdown
    assert "- 실행 ID: `(알 수 없음)`" in markdown
    assert "- 대상: `(미설정)`" in markdown
    assert "- 종료 시 실행 중 작업 패키지: `(없음)`" in markdown
    assert "- 재시도 후보: `(없음)`" in markdown
    assert "- 완료 작업 패키지: `(없음)`" in markdown
    assert "- 최근 이벤트: `(없음)`" in markdown
    assert ("워크플로우", "(새 워크플로우)") in rows
    assert ("목표", "(없음)") in rows
    assert ("실행 ID", "(알 수 없음)") in rows
    assert ("대상", "(미설정)") in rows
    assert ("실행 중 작업 패키지", "(없음)") in rows
    assert ("재시도 후보", "(없음)") in rows
    assert ("완료 작업 패키지", "(없음)") in rows
    assert ("최근 이벤트", "(없음)") in rows


def test_context_markdown_includes_full_workflow_history() -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-history",
        goal="Resume workflow",
        state="blueprint_ready",
        workflow_events=[f"event-{index}" for index in range(1, 13)],
        execution_log=[
            *(f"event-{index}" for index in range(1, 13)),
            "WP-001 claude: failed - missing file",
        ],
    )

    markdown = snapshot_context_markdown(snapshot)

    assert "### Workflow History" in markdown
    assert "- event-1" in markdown
    assert "- event-12" in markdown
    assert "### Execution Results" in markdown
    assert "WP-001 claude: failed - missing file" in markdown


def test_context_markdown_uses_korean_labels() -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-ko",
        goal="컨텍스트 확인",
        state="blueprint_ready",
        synthesis=SynthesisSnapshot(
            summary="현재 종합",
            consensus_progress="blueprint ready",
        ),
        questions=[
            QuestionSnapshot(
                id="q1",
                question="진행할까요?",
                answer="네",
                status="answered",
            )
        ],
        decisions=["결정 A"],
        work_packages=["WP-001 codex"],
        workflow_events=["event-1"],
        execution_log=["event-1", "WP-001 codex: done"],
    )

    markdown = snapshot_context_markdown(snapshot, lang="ko")

    assert "- 워크플로우: `wf-ko`" in markdown
    assert "- 상태: `설계 준비`" in markdown
    assert "- 종합: `설계 준비됨`" in markdown
    assert "blueprint ready" not in markdown
    assert "### 종합" in markdown
    assert "### 질문" in markdown
    assert "- **q1** [답변됨] 진행할까요?" in markdown
    assert "  - 답변: 네" in markdown
    assert "### 결정" in markdown
    assert "### 작업 패키지" in markdown
    assert "### 워크플로우 이력" in markdown
    assert "### 실행 결과" in markdown

    placeholder_markdown = snapshot_context_markdown(
        WorkflowNexusSnapshot(
            round_num=1,
            subtasks=[
                SubtaskSnapshot(
                    id="",
                    parent_package_id="",
                    parent_agent="",
                    delegated_to="",
                    objective="",
                    result_summary="",
                    status="waiting",
                )
            ],
            final_review=ReviewSnapshot(
                reviewer_agent="",
                status="approved",
            ),
            post_review_items=[
                PostReviewActionSnapshot(
                    id="AI-001",
                    severity="high",
                    status="pending",
                    title="테스트 보강",
                )
            ],
        ),
        lang="ko",
    )
    assert "- 워크플로우: `(새 워크플로우)`" in placeholder_markdown
    assert "- 목표: (없음)" in placeholder_markdown
    assert "- **(이름 없음)** [대기] (패키지 없음) -> (알 수 없음): (없음)" in (
        placeholder_markdown
    )
    assert "- `승인` / 리뷰어 `(알 수 없음)`" in placeholder_markdown
    assert "- **AI-001** [높음][대기] 테스트 보강" in placeholder_markdown


def test_context_presenter_uses_korean_empty_labels() -> None:
    message = "현재 세션 컨텍스트가 없습니다. 먼저 프롬프트를 시작하거나 워크플로우를 재개하세요."

    assert context_title(lang="ko") == "컨텍스트"
    assert context_no_current_markdown(lang="ko") == message
    assert snapshot_context_markdown(WorkflowNexusSnapshot(), lang="ko") == message


def test_memory_presenter_uses_korean_labels() -> None:
    assert memory_title(lang="ko") == "메모리 통계"
    assert memory_title("compact", lang="ko") == "메모리 압축"
    assert memory_title("cleanup", lang="ko") == "메모리 정리"
    assert memory_cleanup_error_markdown(
        "--keep-latest requires a number.",
        lang="ko",
    ) == "`--keep-latest`에는 숫자를 입력하세요."
    assert memory_cleanup_error_markdown(
        "Usage: `/memory cleanup --oversized-backups [--apply] [--keep-latest N]`",
        lang="ko",
    ) == "사용법: `/memory cleanup --oversized-backups [--apply] [--keep-latest N]`"
    assert memory_cleanup_error_markdown(
        "Unknown cleanup option: `--oops`",
        lang="ko",
    ) == "알 수 없는 정리 옵션: `--oops`"


def test_artifact_presenter_uses_korean_labels() -> None:
    assert artifact_title(lang="ko") == "아티팩트"
    assert artifact_usage_markdown(lang="ko") == "사용법: `/artifact <memory-id>`"


def test_model_settings_presenter_uses_korean_labels() -> None:
    assert model_settings_title(lang="ko") == "모델 설정"
    assert model_settings_unavailable_markdown(lang="ko") == (
        "모델 설정은 시작 화면과 Nexus에서 사용할 수 있습니다."
    )
    assert model_settings_updated_markdown(lang="ko") == (
        "모델 설정을 업데이트했습니다."
    )


def test_slash_command_notification_title_uses_korean_label() -> None:
    assert slash_command_notification_title(lang="ko") == "슬래시 명령"


def test_workflow_presenter_uses_korean_labels() -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-ko",
        goal="워크플로우 확인",
        state="blueprint_ready",
        round_num=3,
        questions=[QuestionSnapshot(id="q1", question="진행할까요?")],
        decisions=["결정 A"],
        work_packages=["WP-001 codex"],
        subtasks=[
            SubtaskSnapshot(
                id="sub-1",
                parent_package_id="WP-001",
                parent_agent="claude",
                delegated_to="codex",
                objective="테스트",
                result_summary="완료",
                status="done",
            )
        ],
        work_package_repairs=["repair note"],
        execution_log=["event-1"],
        execution_recovery=ExecutionRecoverySnapshot(
            run_id="exec-run-test",
            state="interrupted",
            retry_candidates=("WP-001",),
        ),
    )

    markdown = snapshot_workflow_markdown(snapshot, lang="ko")
    rows = snapshot_workflow_rows(snapshot, lang="ko")

    assert "- 상태: `설계 준비`" in markdown
    assert "- 목표: 워크플로우 확인" in markdown
    assert "- 대기 중 질문: `1`" in markdown
    assert "- 결정: `1`" in markdown
    assert "- 작업 패키지: `1`" in markdown
    assert "- 하위 작업: `1`" in markdown
    assert "- 로컬 정책 복구: `1`" in markdown
    assert "- 실행 로그 항목: `1`" in markdown
    assert "### 실행 복구" in markdown
    assert "재시도 후보: `WP-001`" in markdown
    assert ("상태", "설계 준비") in rows
    assert ("대기 중 질문", "1") in rows
    assert ("실행 ID", "exec-run-test") in rows

    empty_markdown = snapshot_workflow_markdown(WorkflowNexusSnapshot(), lang="ko")
    empty_rows = snapshot_workflow_rows(WorkflowNexusSnapshot(), lang="ko")
    assert "- ID: `(새 워크플로우)`" in empty_markdown
    assert "- 목표: (없음)" in empty_markdown
    assert ("ID", "(새 워크플로우)") in empty_rows
    assert ("목표", "(없음)") in empty_rows


def test_questions_presenter_uses_korean_labels() -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-ko",
        questions=[
            QuestionSnapshot(
                id="q1",
                question="테마를 선택할까요?",
                answer="dark",
                options=["dark", "light"],
                recommended_option="dark",
                status="answered",
            ),
            QuestionSnapshot(
                id="q2",
                question="추가 요청이 있나요?",
            ),
        ],
    )

    markdown = questions_markdown(snapshot, lang="ko")
    select_markdown = questions_select_markdown(snapshot, lang="ko")
    rows = questions_rows(snapshot, lang="ko")

    assert "   - 답변: dark" in markdown
    assert "   - 추천: dark" in markdown
    assert "1. **q1** [답변됨] 테마를 선택할까요?" in markdown
    assert "2. **q2** [열림] 추가 요청이 있나요?" in markdown
    assert "질문 패널 버튼을 사용하거나" in markdown
    assert "선택된 질문: **q1**" in select_markdown
    assert "질문 패널의 선택지 버튼" in select_markdown
    assert rows[0] == ("q1", "답변됨", "테마를 선택할까요?", "dark, light")
    assert rows[1] == ("q2", "열림", "추가 요청이 있나요?", "(자유 입력)")
    assert questions_table_columns(lang="ko") == ("ID", "상태", "질문", "선택지")
    assert questions_action_hint(has_questions=True, lang="ko").startswith("질문 패널")
    assert "중앙 에이전트" in questions_action_hint(has_questions=False, lang="ko")


def test_questions_empty_presenter_uses_korean_labels() -> None:
    snapshot = WorkflowNexusSnapshot()

    assert questions_markdown(snapshot, lang="ko") == "대기 중인 워크플로우 질문이 없습니다."
    assert questions_select_markdown(snapshot, lang="ko") == "선택할 대기 질문이 없습니다."


def test_decisions_presenter_uses_korean_labels() -> None:
    empty = WorkflowNexusSnapshot()
    snapshot = WorkflowNexusSnapshot(decisions=["결정 A"])

    assert decisions_markdown(empty, lang="ko") == (
        "현재 세션에 기록된 워크플로우 결정이 없습니다."
    )
    assert decisions_markdown(snapshot, lang="ko") == "1. 결정 A"
    assert decisions_rows(snapshot, lang="ko") == (("1", "결정 A"),)
    assert decisions_table_columns(lang="ko") == ("#", "결정")
    assert decisions_action_hint(has_decisions=False, lang="ko").startswith("대기 중인 질문")
    assert decisions_action_hint(has_decisions=True, lang="ko") == ""


def test_packages_presenter_uses_korean_labels() -> None:
    empty = WorkflowNexusSnapshot()
    snapshot = WorkflowNexusSnapshot(
        central_work_packages=["WP-001 claude: 설계"],
        work_packages=["WP-002 codex: 구현"],
    )

    assert packages_markdown(empty, lang="ko") == (
        "현재 세션에 생성된 워크플로우 작업 패키지가 없습니다."
    )
    assert "1. **중앙** WP-001 claude: 설계" in packages_markdown(snapshot, lang="ko")
    assert "2. **로컬** WP-002 codex: 구현" in packages_markdown(snapshot, lang="ko")
    assert packages_rows(snapshot, lang="ko") == (
        ("1", "중앙", "WP-001 claude: 설계"),
        ("2", "로컬", "WP-002 codex: 구현"),
    )
    assert packages_table_columns(lang="ko") == ("#", "출처", "작업 패키지")
    assert packages_action_hint(has_packages=False, lang="ko").startswith("설계안")
    assert packages_action_hint(has_packages=True, lang="ko") == ""


def test_subtasks_presenter_uses_korean_labels() -> None:
    empty = WorkflowNexusSnapshot()
    snapshot = WorkflowNexusSnapshot(
        subtasks=[
            SubtaskSnapshot(
                id="ST-001",
                parent_package_id="WP-001",
                parent_agent="claude",
                delegated_to="codex",
                objective="테스트",
                result_summary="완료",
                status="done",
            ),
            SubtaskSnapshot(
                id="",
                parent_package_id="",
                parent_agent="",
                delegated_to="",
                objective="",
                result_summary="",
                status="waiting",
            )
        ]
    )

    assert subtasks_markdown(empty, lang="ko") == (
        "현재 세션에 기록된 프로바이더 위임 하위 작업이 없습니다."
    )
    assert "1. **ST-001** [완료] WP-001 -> codex: 완료" in subtasks_markdown(
        snapshot,
        lang="ko",
    )
    assert "2. **(이름 없음)** [대기] (패키지 없음) -> (알 수 없음): (없음)" in (
        subtasks_markdown(snapshot, lang="ko")
    )
    assert subtasks_rows(snapshot, lang="ko") == (
        ("ST-001", "WP-001", "codex", "완료", "완료"),
        ("(이름 없음)", "(없음)", "(알 수 없음)", "대기", "(없음)"),
    )
    assert subtasks_table_columns(lang="ko") == (
        "ID",
        "작업 패키지",
        "위임 대상",
        "상태",
        "요약",
    )
    assert subtasks_action_hint(has_subtasks=False, lang="ko").startswith("실행 중인")
    assert subtasks_action_hint(has_subtasks=True, lang="ko") == ""


def test_history_presenter_uses_korean_labels() -> None:
    command = LocalCommandSnapshot(command="/status", title="Status", body="status")
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-ko",
        goal="이력 확인",
        state="reviewing",
        round_num=2,
        execution_log=["WP-001 codex: done"],
    )

    rows = history_rows(snapshot, [command], lang="ko")
    markdown = history_markdown(snapshot, rows, lang="ko")

    assert rows == (
        ("워크플로우", "wf-ko"),
        ("상태", "리뷰 중"),
        ("라운드", "2"),
        ("목표", "이력 확인"),
        ("로컬 명령", "/status - Status"),
        ("실행", "WP-001 codex: done"),
    )
    assert "- 워크플로우: `wf-ko`" in markdown
    assert "- 상태: `리뷰 중`" in markdown
    assert "### 최근 실행 로그" in markdown
    assert "### 최근 로컬 항목" in markdown
    assert "- **로컬 명령**: /status - Status" in markdown
    placeholder_rows = history_rows(
        WorkflowNexusSnapshot(goal="이력 확인"),
        (),
        lang="ko",
    )
    placeholder_markdown = history_markdown(
        WorkflowNexusSnapshot(goal="이력 확인"),
        placeholder_rows,
        lang="ko",
    )
    assert ("워크플로우", "(새 워크플로우)") in placeholder_rows
    assert "- 워크플로우: `(새 워크플로우)`" in placeholder_markdown
    assert history_table_columns(lang="ko") == ("종류", "항목")
    assert history_action_hint(has_history=False, lang="ko").startswith("프롬프트 실행")
    assert history_action_hint(has_history=True, lang="ko") == ""


def test_history_empty_presenter_uses_korean_labels() -> None:
    assert history_markdown(WorkflowNexusSnapshot(), (), lang="ko") == (
        "현재 세션에 기록된 로컬 이력이 없습니다."
    )


def test_review_presenter_uses_korean_labels() -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-review",
        state="reviewing",
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Plan",
                owner_agent="claude",
                status="done",
            ),
            WorkPackageSnapshot(
                id="WP-002",
                title="Build",
                owner_agent="codex",
                status="done",
                review_status="approved",
            ),
        ],
        final_review=ReviewSnapshot(
            reviewer_agent="codex",
            status="approved",
        ),
    )

    rows = review_rows(snapshot, lang="ko")

    assert rows == (
        ("워크플로우", "wf-review"),
        ("상태", "리뷰 중"),
        ("작업 패키지", "2"),
        ("대기 중 작업 패키지 리뷰", "WP-001"),
        ("리뷰된 작업 패키지", "WP-002:승인"),
        ("최종 리뷰", "승인 / 리뷰어 codex"),
    )
    placeholder_rows = review_rows(WorkflowNexusSnapshot(), lang="ko")
    reviewer_rows = review_rows(
        WorkflowNexusSnapshot(
            final_review=ReviewSnapshot(
                reviewer_agent="",
                status="approved",
            )
        ),
        lang="ko",
    )
    assert ("워크플로우", "(새 워크플로우)") in placeholder_rows
    assert ("대기 중 작업 패키지 리뷰", "(없음)") in placeholder_rows
    assert ("리뷰된 작업 패키지", "(없음)") in placeholder_rows
    assert ("최종 리뷰", "(없음)") in placeholder_rows
    assert ("최종 리뷰", "승인 / 리뷰어 (알 수 없음)") in reviewer_rows
    assert review_table_columns(lang="ko") == ("항목", "값")
    assert review_title(lang="ko") == "리뷰"
    assert review_action_hint(lang="ko").startswith("`/review wp`")


def test_answer_presenter_uses_korean_labels() -> None:
    assert answer_title(lang="ko") == "답변"
    assert answer_usage_markdown(lang="ko") == (
        "사용법: /answer <question-id|index|next> <answer>"
    )
    assert answer_action_hint(lang="ko") == (
        "먼저 `/questions`를 실행해 대기 중인 질문을 확인하세요."
    )


def test_ask_presenter_uses_korean_labels() -> None:
    assert ask_title(lang="ko") == "질문"
    assert ask_usage_markdown(lang="ko") == (
        "사용법: /ask <all|agent[,agent...]> [--model MODEL] <prompt>"
    )
    assert ask_unknown_agent_markdown(["missing"], lang="ko") == (
        "알 수 없거나 비활성화된 에이전트: missing"
    )
    assert ask_no_active_agents_markdown(lang="ko") == (
        "/ask에 사용할 활성 에이전트가 없습니다."
    )
    assert ask_missing_model_markdown(lang="ko") == "--model 뒤에 모델을 입력하세요."
    assert ask_prompt_empty_markdown(lang="ko") == "프롬프트를 입력하세요."
    assert ask_action_hint(lang="ko") == (
        "/ask <all|agent[,agent...]> [--model MODEL] <prompt>"
    )


def test_execute_presenter_uses_korean_labels() -> None:
    assert execute_title(lang="ko") == "실행"
    assert execute_finish_planning_action_hint(lang="ko") == (
        "작업 패키지가 준비되면 Nexus에서 `/execute`를 실행하세요."
    )
    assert execute_retry_title(lang="ko") == "실행 재시도"
    assert execute_retry_no_packages_markdown(lang="ko") == (
        "현재 워크플로우에 사용할 수 있는 작업 패키지가 없습니다."
    )
    assert execute_retry_no_packages_action_hint(lang="ko") == (
        "하나 이상의 작업 패키지를 준비하고 실행하세요."
    )
    assert execution_recovery_title(lang="ko") == "실행 복구"
    assert execution_recovery_action_hint(lang="ko") == (
        "`/execute-retry`, `/execute mark-interrupted`, "
        "`/execute abort` 중 하나를 실행하세요."
    )
    assert execution_recovery_table_columns(lang="ko") == ("항목", "값")
    recovery_snapshot = WorkflowNexusSnapshot(
        execution_recovery=ExecutionRecoverySnapshot(
            state="repair_blocked",
            run_id="run-1",
        )
    )
    assert "- 실행: `복구 차단`" in execution_recovery_markdown(
        recovery_snapshot,
        lang="ko",
    )
    assert ("실행", "복구 차단") in execution_recovery_rows(
        recovery_snapshot,
        lang="ko",
    )


def test_report_presenter_uses_korean_labels() -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-report",
        state="done",
        decisions=["Ship it."],
        central_work_packages=["Plan"],
        work_packages=["Build"],
    )

    assert report_title(lang="ko") == "리포트"
    assert report_no_export_data_markdown(lang="ko") == (
        "내보낼 워크플로우 데이터가 없습니다."
    )
    assert report_no_open_data_markdown(lang="ko") == (
        "리포트로 표시할 워크플로우 데이터가 없습니다."
    )
    assert report_export_unavailable_title(lang="ko") == "내보내기 불가"
    assert report_export_complete_title(lang="ko") == "내보내기 완료"
    assert report_export_action_hint(lang="ko").startswith("리포트를 내보내려면")
    assert report_open_action_hint(lang="ko").startswith("리포트를 열려면")
    assert report_opened_markdown(lang="ko") == "리포트 화면을 열었습니다."
    assert report_saved_markdown("/tmp/report.md", lang="ko") == (
        "리포트 저장됨: `/tmp/report.md`"
    )
    assert report_saved_notification("/tmp/report.md", lang="ko") == (
        "리포트 저장됨: /tmp/report.md"
    )
    assert report_saved_rows("/tmp/report.md", lang="ko") == (
        ("경로", "/tmp/report.md"),
    )
    assert _section_label("Review Repairs", lang="ko") == "리뷰 보정"
    assert _field_label("Risk", lang="ko") == "리스크"
    assert _field_label("Risks", lang="ko") == "리스크"
    rendered = _render_synthesis(
        SynthesisSnapshot(
            summary="추가 합의가 필요합니다.",
            consensus_progress="round 1 consensus not reached (1/3); fallback used",
            source="runtime",
        ),
        lang="ko",
    )
    assert "1라운드 합의 미도달 (1/3) · 대체 종합 사용" in rendered
    assert "[bold]출처[/bold]: 런타임" in rendered
    assert "round 1 consensus not reached" not in rendered
    assert report_summary_rows(snapshot, lang="ko") == (
        ("워크플로우", "wf-report"),
        ("상태", "완료"),
        ("질문", "0"),
        ("결정", "1"),
        ("작업 패키지", "2"),
        ("하위 작업", "0"),
    )
    assert report_summary_rows(WorkflowNexusSnapshot(), lang="ko")[0] == (
        "워크플로우",
        "(새 워크플로우)",
    )


def test_save_presenter_uses_korean_labels() -> None:
    assert save_title(lang="ko") == "저장"
    assert save_auto_persist_markdown(lang="ko") == (
        "Trinity 워크플로우는 자동으로 저장됩니다. "
        "마크다운 리포트 내보내기는 /report save를 사용하세요."
    )


def test_target_presenter_uses_korean_labels() -> None:
    assert target_title(lang="ko") == "대상"
    assert target_selection_cancelled_markdown(lang="ko") == (
        "대상 작업 폴더 선택을 취소했습니다."
    )
    assert target_preflight_cancelled_markdown(lang="ko") == (
        "작업 폴더 사전 확인을 취소했습니다."
    )
    assert target_control_repo_action_hint(lang="ko").startswith("Trinity 제어 저장소")
    assert target_current_markdown(None, lang="ko") == "현재 대상: `(미설정)`"
    assert target_action_hint(lang="ko").startswith("실행 전에 `/target <path>`")
    assert target_cleared_markdown(lang="ko") == "대상 작업 폴더를 초기화했습니다."
    assert target_not_directory_markdown("/tmp/file", lang="ko") == (
        "대상 경로가 이미 존재하지만 디렉터리가 아닙니다: `/tmp/file`"
    )
    assert target_prepare_failed_markdown("denied", lang="ko") == (
        "대상 작업 폴더를 준비할 수 없습니다: denied"
    )
    assert target_workspace_markdown("/tmp/app", lang="ko") == (
        "대상 작업 폴더: `/tmp/app`"
    )
    assert target_rows(
        "/tmp/app",
        inside_control_repo=False,
        control_repo_confirmed=True,
        lang="ko",
    ) == (
        ("경로", "/tmp/app"),
        ("제어 저장소 내부", "아니오"),
        ("제어 저장소 확인", "예"),
    )


def test_target_cancelled_local_command_snapshot_uses_korean_labels() -> None:
    selection = target_cancelled_local_command_snapshot(lang="ko")
    preflight = target_cancelled_local_command_snapshot(
        kind="preflight",
        lang="ko",
    )

    assert selection.command == "/target"
    assert selection.title == "대상"
    assert selection.body == "대상 작업 폴더 선택을 취소했습니다."
    assert selection.severity == "warning"
    assert selection.empty is True
    assert selection.action_hint.startswith("Trinity 제어 저장소")
    assert preflight.body == "작업 폴더 사전 확인을 취소했습니다."


def test_rounds_presenter_uses_korean_labels() -> None:
    assert rounds_title(lang="ko") == "라운드"
    assert rounds_current_markdown(3, lang="ko") == "현재 최대 라운드: `3`."
    assert rounds_set_markdown(7, lang="ko") == (
        "이 세션의 최대 라운드를 `7`로 설정했습니다."
    )
    assert rounds_invalid_number_markdown(lang="ko") == "숫자가 올바르지 않습니다."
    assert rounds_range_error_markdown(lang="ko") == "라운드는 1에서 20 사이여야 합니다."
    assert rounds_change_action_hint(lang="ko") == (
        "`/rounds <1..20>`로 이 세션의 값을 변경하세요."
    )
    assert rounds_usage_action_hint(lang="ko") == "`/rounds <1..20>`를 사용하세요."
    assert rounds_rows(7, lang="ko") == (
        ("현재 최대 라운드", "7"),
        ("허용 범위", "1..20"),
    )


def test_agent_presenter_uses_korean_labels() -> None:
    assert agent_title(lang="ko") == "에이전트"
    assert agent_current_settings_markdown(lang="ko") == "현재 에이전트 세션 설정입니다."
    assert agent_change_action_hint(lang="ko") == (
        "`/agent <name> on|off`로 에이전트 하나를 변경하세요."
    )
    assert agent_usage_markdown(lang="ko") == "사용법: `/agent <name> on|off`"
    assert agent_unknown_markdown("missing", lang="ko") == (
        "알 수 없는 에이전트: `missing`"
    )
    assert agent_status_markdown("claude", False, lang="ko") == (
        "이 세션에서 에이전트 `claude`를 비활성화했습니다."
    )
    assert agent_table_columns(lang="ko") == ("에이전트", "활성화", "프로바이더")
    assert agent_enabled_value(True, lang="ko") == "예"
    assert agent_enabled_value(False, lang="ko") == "아니오"


def test_agent_session_presenters_render_rows_and_notice() -> None:
    agents = {
        "codex": SimpleNamespace(enabled=False, provider=Provider.CODEX),
        "claude": SimpleNamespace(enabled=True, provider=Provider.CLAUDE_CODE),
    }

    assert session_setting_body("Changed").endswith(SESSION_ONLY_SETTING_NOTICE)
    assert agent_rows(agents, lang="en") == (
        ("claude", "yes", "claude-code"),
        ("codex", "no", "codex"),
    )


def test_local_command_snapshot_presenter_normalizes_empty_body() -> None:
    snapshot = local_command_snapshot(
        "/status",
        "Status",
        "   ",
        severity="warning",
        table_columns=("Item", "Value"),
        table_rows=(("State", "idle"),),
    )

    assert snapshot.body == "(no output)"
    assert snapshot.severity == "warning"
    assert snapshot.table_rows == (("State", "idle"),)


def test_local_command_notification_severity_maps_warning_and_error() -> None:
    assert local_command_notification_severity(
        local_command_snapshot("/status", "Status", "ok")
    ) == "information"
    assert local_command_notification_severity(
        local_command_snapshot("/status", "Status", "warn", severity="warning")
    ) == "warning"
    assert local_command_notification_severity(
        local_command_snapshot("/status", "Status", "error", severity="error")
    ) == "warning"


def test_caveman_presenter_uses_korean_labels() -> None:
    assert caveman_title(lang="ko") == "간결 모드"
    assert caveman_current_markdown("on", "lite", lang="ko") == (
        "간결 모드: `on` (`lite`)."
    )
    assert caveman_set_markdown("on", "full", lang="ko") == (
        "이 세션의 간결 모드를 `on` (`full`)로 설정했습니다."
    )
    assert caveman_usage_markdown(lang="ko") == (
        "사용법: /caveman [on|off|lite|full|ultra]"
    )
    assert caveman_allowed_action_hint(lang="ko") == (
        "허용 모드: on, off, lite, full, ultra."
    )
    assert caveman_change_action_hint(lang="ko") == (
        "`/caveman <mode>`로 이 세션의 값을 변경하세요."
    )
    assert caveman_rows("on", "lite", lang="ko") == (
        ("모드", "on"),
        ("강도", "lite"),
        ("허용값", "on, off, lite, full, ultra"),
    )


def test_resume_presenter_uses_korean_labels() -> None:
    archives = [
        TextualWorkflowArchiveOption(
            selector="1",
            session_id="wf-1",
            state="done",
            goal="",
            updated_at=1.0,
        )
    ]
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-resumed",
        state="blueprint_ready",
        goal="게임 만들기",
        round_num=2,
    )

    assert resume_title(lang="ko") == "재개"
    assert resume_no_saved_markdown(lang="ko") == "재개할 저장된 워크플로우가 없습니다."
    assert resume_no_saved_action_hint(lang="ko").startswith("`/resume`을 사용하려면")
    assert resume_archives_markdown(archives, lang="ko").splitlines()[0] == (
        "재개할 수 있는 저장된 워크플로우가 있습니다."
    )
    assert resume_archive_table_columns(lang="ko") == (
        "선택자",
        "워크플로우",
        "상태",
        "목표",
    )
    assert resume_archive_rows(archives, lang="ko") == (
        ("1", "wf-1", "완료", "(목표 없음)"),
    )
    assert resume_pick_action_hint(lang="ko") == (
        "재개 모달에서 워크플로우를 선택하세요."
    )
    assert resume_cancelled_markdown(lang="ko") == "재개 선택을 취소했습니다."
    assert resume_cancel_action_hint(lang="ko").startswith("보관된 워크플로우")
    assert resume_result_table_columns(lang="ko") == ("항목", "값")
    assert resume_result_rows(snapshot, lang="ko") == (
        ("워크플로우", "wf-resumed"),
        ("상태", "설계 준비"),
        ("목표", "게임 만들기"),
        ("라운드", "2"),
    )
    assert resume_result_rows(WorkflowNexusSnapshot(), lang="ko") == (
        ("워크플로우", "(새 워크플로우)"),
        ("상태", "대기"),
        ("목표", "(없음)"),
        ("라운드", "0"),
    )


def test_help_unknown_presenter_uses_korean_labels() -> None:
    suggestions = ("/status",)

    assert syntax_error_title(lang="ko") == "구문 오류"
    assert unknown_command_title(lang="ko") == "알 수 없는 명령"
    assert unknown_command_table_columns(lang="ko") == ("추천", "요약")
    assert unknown_command_markdown("/stats", suggestions, lang="ko").startswith(
        "`/stats`은 Trinity 슬래시 명령이 아닙니다."
    )
    assert "다음 명령을 찾으셨나요:" in unknown_command_markdown(
        "/stats",
        suggestions,
        lang="ko",
    )
    assert unknown_command_rows(suggestions, lang="ko")[0][0] == "/status"
    assert help_title(lang="ko") == "Trinity 명령"
    assert help_table_columns(lang="ko") == (
        "명령",
        "카테고리",
        "에이전트 호출",
        "요약",
    )
    assert help_markdown(lang="ko").startswith(
        "Trinity 소유 슬래시 명령은 프로바이더 프롬프트보다 먼저 처리됩니다."
    )
    assert help_rows(lang="ko")


def test_improve_presenter_uses_korean_labels() -> None:
    empty = WorkflowNexusSnapshot(
        session_id="wf-improve",
        state="post_review_ready",
        supplemental_round=1,
    )
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-improve",
        state="post_review_ready",
        supplemental_round=2,
        post_review_items=[
            PostReviewActionSnapshot(
                id="AI-001",
                title="Fix tests",
                summary="Fix tests",
                severity="high",
                status="pending",
                kind="test",
            )
        ],
    )

    assert improve_rows(empty, lang="ko") == (
        ("워크플로우", "wf-improve"),
        ("상태", "후속 조치 대기"),
        ("보충 라운드", "1"),
        ("조치 항목", "(없음)"),
    )
    assert improve_rows(snapshot, lang="ko") == (
        ("워크플로우", "wf-improve"),
        ("상태", "후속 조치 대기"),
        ("보충 라운드", "2"),
        ("AI-001", "대기; 심각도=높음; 종류=테스트; 제목=Fix tests"),
    )
    assert improve_table_columns(lang="ko") == ("항목", "값")
    assert improve_title(lang="ko") == "개선"
    assert improve_action_hint(lang="ko").startswith("`/improve high`")


def test_workflow_outcome_message_uses_korean_labels() -> None:
    assert (
        workflow_outcome_message_markdown(
            "No blueprint is ready. Finish planning before execution.",
            lang="ko",
        )
        == "준비된 설계안이 없습니다. 실행 전에 계획을 완료하세요."
    )
    assert (
        workflow_outcome_message_markdown("Review started: wp.", lang="ko")
        == "리뷰를 시작했습니다: wp."
    )
    assert (
        workflow_outcome_message_markdown(
            "Review requested repairs; restarting execution for: WP-001. "
            "Blocked by repair guard: WP-002. "
            "Choose a target workspace before restarting repairs.",
            lang="ko",
        )
        == "리뷰가 수정을 요청했습니다. 다음 작업 패키지의 실행을 다시 시작합니다: "
        "WP-001. 보정 루프 가드에 의해 차단됨: WP-002. "
        "보정 재시작 전에 대상 작업 폴더를 선택하세요."
    )
    assert (
        workflow_outcome_message_markdown(
            "No review-repair blocked packages to retry.",
            lang="ko",
        )
        == "재시도할 리뷰 보정 차단 패키지가 없습니다."
    )
    assert (
        workflow_outcome_message_markdown(
            "Accepted blocked review repairs.",
            lang="ko",
        )
        == "차단된 리뷰 보정을 완료 처리했습니다."
    )
    assert (
        workflow_outcome_message_markdown(
            "Stopped workflow after blocked review repairs: WP-002.",
            lang="ko",
        )
        == "리뷰 보정 차단 이후 워크플로우를 중단했습니다: WP-002."
    )
    assert (
        workflow_outcome_message_markdown("Workflow is still running.", lang="en")
        == "Workflow is still running."
    )
    assert (
        workflow_outcome_message_markdown(
            "Continuing without failed providers.",
            lang="ko",
        )
        == "실패한 프로바이더를 제외하고 계속합니다."
    )
    assert (
        workflow_outcome_message_markdown(
            "Workflow stopped after provider errors.",
            lang="ko",
        )
        == "프로바이더 오류 이후 워크플로우를 중단했습니다."
    )
    assert (
        workflow_outcome_message_markdown(
            "Retrying failed providers.",
            lang="ko",
        )
        == "실패한 프로바이더를 재시도합니다."
    )


def test_model_discovery_applies_fast_provider_before_slow_provider(
    tmp_path,
    monkeypatch,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents["codex"].enabled = True
    config.agents["antigravity"].enabled = True
    app = TrinityTextualApp(config, FakeWorkflowController())
    applied: list[str] = []

    def fake_discover(provider, cli_command, *, timeout_seconds, use_cache):
        if provider == Provider.CLAUDE_CODE:
            time.sleep(0.05)
        return [
            ProviderModelChoice(
                provider=provider,
                model="default",
                label=f"{cli_command}(default)",
                source="static-fallback",
                is_default=True,
            )
        ]

    def direct_call(callback, choices_by_agent):
        applied.extend(choices_by_agent)
        callback(choices_by_agent)

    monkeypatch.setattr("trinity.textual_app.model_discovery.discover_provider_models", fake_discover)
    monkeypatch.setattr(app, "call_from_thread", direct_call)
    monkeypatch.setattr(
        app,
        "_apply_discovered_model_choices",
        lambda choices_by_agent: app._agent_model_choices.update(choices_by_agent),
    )

    app._discover_provider_models(use_cache=False)

    assert applied[-1] == "claude"
    assert {"claude", "codex", "antigravity"} <= set(applied)
    assert set(app._agent_model_choices) >= {"claude", "codex", "antigravity"}


@pytest.mark.asyncio
async def test_textual_app_boots_to_start_screen(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(100, 30)):
        assert app.current_route == "start"
        assert app.screen.name == "start"
        assert app.screen.query_one(PromptComposer)
        geometry = app.screen.query_one("#start-geometry", SacredGeometryAnimation)
        assert geometry.styles.height.value == 14
        assert str(geometry.render()).strip()


@pytest.mark.asyncio
async def test_start_screen_stays_within_standard_viewport(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()

        start = app.screen
        assert isinstance(start, StartScreen)
        widgets = (
            start.query_one("#start-geometry", Static),
            start.query_one("#start-title", Static),
            start.query_one("#start-composer", PromptComposer),
            start.query_one("#start-recipient-selector", AgentRecipientModelSelector),
            start.query_one("#start-actions"),
            start.query_one("#start-select-workspace", Button),
            start.query_one("#workspace-candidate", Static),
        )
        for widget in widgets:
            assert widget.region.x >= 0
            assert widget.region.x + widget.region.width <= start.size.width
            assert widget.region.y >= 0
            assert widget.region.y + widget.region.height <= start.size.height


@pytest.mark.parametrize(
    ("size", "geometry_visible"),
    [((60, 20), False), ((120, 20), False), ((120, 32), False), ((120, 33), True)],
)
@pytest.mark.asyncio
async def test_start_screen_compacts_geometry_in_low_viewport(
    tmp_path,
    size: tuple[int, int],
    geometry_visible: bool,
) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=size) as pilot:
        await pilot.pause()

        start = app.screen
        assert isinstance(start, StartScreen)
        start_shell = start.query_one("#start-screen")
        geometry = start.query_one("#start-geometry", Static)
        assert geometry.display is geometry_visible
        widgets = (
            start.query_one("#start-composer", PromptComposer),
            start.query_one("#start-recipient-selector", AgentRecipientModelSelector),
            start.query_one("#start-actions"),
            start.query_one("#start-select-workspace", Button),
            start.query_one("#workspace-candidate", Static),
        )
        for widget in widgets:
            assert widget.region.y >= start_shell.region.y
            assert (
                widget.region.y + widget.region.height
                <= start_shell.region.y + start_shell.region.height
            )


@pytest.mark.asyncio
async def test_start_screen_compact_geometry_tracks_terminal_resize(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()

        start = app.screen
        assert isinstance(start, StartScreen)
        geometry = start.query_one("#start-geometry", Static)
        assert geometry.display is True

        await pilot.resize_terminal(60, 20)
        await pilot.pause()
        assert geometry.display is False

        await pilot.resize_terminal(120, 36)
        await pilot.pause()
        assert geometry.display is True


@pytest.mark.asyncio
async def test_start_workspace_label_stays_compact_with_long_path(
    tmp_path,
) -> None:
    control_repo = tmp_path / "control"
    target = tmp_path / ("target-" + "very-long-directory-name-" * 6)
    control_repo.mkdir()
    target.mkdir()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=control_repo),
        launch_cwd=target,
    )

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()

        start = app.screen
        assert isinstance(start, StartScreen)
        workspace_label = start.query_one("#workspace-candidate", Static)
        select_workspace = start.query_one("#start-select-workspace", Button)
        assert str(select_workspace.label) == "Select Workspace"
        assert select_workspace.region.height == 3
        assert workspace_label.region.height == 3
        assert select_workspace.region.x > workspace_label.region.x
        assert (
            workspace_label.region.y + workspace_label.region.height
            <= start.size.height
        )


@pytest.mark.parametrize(
    ("size", "geometry_visible"),
    [
        ((60, 20), False),
        ((120, 20), False),
        ((120, 32), False),
        ((120, 33), True),
        ((120, 36), True),
    ],
)
@pytest.mark.asyncio
async def test_start_command_palette_keyboard_selection_stays_visible(
    tmp_path,
    size: tuple[int, int],
    geometry_visible: bool,
) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=size) as pilot:
        await pilot.pause()

        start = app.screen
        assert isinstance(start, StartScreen)
        composer = start.query_one("#start-composer", PromptComposer)
        composer.set_text("/")
        composer.focus_text_area()
        for _ in range(COMMAND_LIMIT + 4):
            await pilot.press("down")
        await pilot.pause()

        start_shell = start.query_one("#start-screen")
        geometry = start.query_one("#start-geometry", Static)
        assert geometry.display is geometry_visible
        selected_option = composer.query_one(".command-option-selected")
        palette = composer.query_one("#prompt-command-palette")
        more = composer.query_one("#command-option-more")
        widgets = (
            composer,
            palette,
            more,
            selected_option,
            start.query_one("#start-recipient-selector"),
            start.query_one("#start-actions"),
            start.query_one("#workspace-candidate", Static),
        )
        for widget in widgets:
            assert widget.region.x >= start_shell.region.x
            assert (
                widget.region.x + widget.region.width
                <= start_shell.region.x + start_shell.region.width
            )
            assert widget.region.y >= start_shell.region.y
            assert (
                widget.region.y + widget.region.height
                <= start_shell.region.y + start_shell.region.height
            )
        palette_bottom_border = palette.region.y + palette.region.height - 1
        composer_bottom_border = composer.region.y + composer.region.height - 1
        assert palette.region.y + palette.region.height <= composer_bottom_border
        assert selected_option.region.y < palette_bottom_border
        assert more.region.y < palette_bottom_border


@pytest.mark.asyncio
async def test_start_command_palette_stays_visible_after_terminal_resize(
    tmp_path,
) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()

        start = app.screen
        assert isinstance(start, StartScreen)
        composer = start.query_one("#start-composer", PromptComposer)
        composer.set_text("/")
        composer.focus_text_area()
        for _ in range(COMMAND_LIMIT + 4):
            await pilot.press("down")
        await pilot.pause()

        for size, geometry_visible in (((60, 20), False), ((120, 36), True)):
            await pilot.resize_terminal(*size)
            await pilot.pause()
            start_shell = start.query_one("#start-screen")
            geometry = start.query_one("#start-geometry", Static)
            selected_option = composer.query_one(".command-option-selected")
            palette = composer.query_one("#prompt-command-palette")
            more = composer.query_one("#command-option-more")
            assert geometry.display is geometry_visible
            widgets = (
                composer,
                palette,
                selected_option,
                more,
                start.query_one("#start-recipient-selector"),
                start.query_one("#start-actions"),
                start.query_one("#workspace-candidate", Static),
            )
            for widget in widgets:
                assert widget.region.x >= start_shell.region.x
                assert (
                    widget.region.x + widget.region.width
                    <= start_shell.region.x + start_shell.region.width
                )
                assert widget.region.y >= start_shell.region.y
                assert (
                    widget.region.y + widget.region.height
                    <= start_shell.region.y + start_shell.region.height
                )
            palette_bottom_border = palette.region.y + palette.region.height - 1
            composer_bottom_border = composer.region.y + composer.region.height - 1
            assert palette.region.y + palette.region.height <= composer_bottom_border
            assert selected_option.region.y < palette_bottom_border
            assert more.region.y < palette_bottom_border


@pytest.mark.parametrize("size", [(60, 20), (80, 20), (120, 20), (120, 36)])
@pytest.mark.asyncio
async def test_nexus_command_palette_keyboard_selection_stays_visible(
    tmp_path,
    size: tuple[int, int],
) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path, lang="ko"))

    async with app.run_test(size=size) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, NexusScreen)
        composer = screen.query_one("#nexus-composer", PromptComposer)
        composer.set_text("/")
        composer.focus_text_area()
        for _ in range(COMMAND_LIMIT + 4):
            await pilot.press("down")
        await pilot.pause()

        selected_option = composer.query_one(".command-option-selected")
        palette = composer.query_one("#prompt-command-palette")
        more = composer.query_one("#command-option-more")
        widgets = (composer, palette, more, selected_option)
        for widget in widgets:
            assert widget.region.x >= 0
            assert widget.region.x + widget.region.width <= screen.size.width
            assert widget.region.y >= 0
            assert widget.region.y + widget.region.height <= screen.size.height
        palette_bottom_border = palette.region.y + palette.region.height - 1
        composer_bottom_border = composer.region.y + composer.region.height - 1
        assert palette.region.y + palette.region.height <= composer_bottom_border
        assert selected_option.region.y < palette_bottom_border
        assert more.region.y < palette_bottom_border


@pytest.mark.asyncio
async def test_nexus_command_palette_stays_visible_after_terminal_resize(
    tmp_path,
) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path, lang="ko"))

    async with app.run_test(size=(120, 36)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, NexusScreen)
        composer = screen.query_one("#nexus-composer", PromptComposer)
        composer.set_text("/")
        composer.focus_text_area()
        for _ in range(COMMAND_LIMIT + 4):
            await pilot.press("down")
        await pilot.pause()

        for size in ((60, 20), (120, 36)):
            await pilot.resize_terminal(*size)
            await pilot.pause()
            nexus_shell = screen.query_one("#nexus-screen")
            selected_option = composer.query_one(".command-option-selected")
            palette = composer.query_one("#prompt-command-palette")
            more = composer.query_one("#command-option-more")
            for widget in (composer, palette, selected_option, more):
                assert widget.region.x >= nexus_shell.region.x
                assert (
                    widget.region.x + widget.region.width
                    <= nexus_shell.region.x + nexus_shell.region.width
                )
                assert widget.region.y >= nexus_shell.region.y
                assert (
                    widget.region.y + widget.region.height
                    <= nexus_shell.region.y + nexus_shell.region.height
                )
            palette_bottom_border = palette.region.y + palette.region.height - 1
            composer_bottom_border = composer.region.y + composer.region.height - 1
            assert palette.region.y + palette.region.height <= composer_bottom_border
            assert selected_option.region.y < palette_bottom_border
            assert more.region.y < palette_bottom_border


@pytest.mark.asyncio
async def test_start_and_nexus_show_agent_recipient_model_selector(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents["codex"].enabled = True
    app = TrinityTextualApp(config, FakeWorkflowController())

    async with app.run_test(size=(120, 34)) as pilot:
        start_selector = app.screen.query_one(
            "#start-recipient-selector",
            AgentRecipientModelSelector,
        )
        assert start_selector.query_one(".recipient-label").styles.min_width.value == 4
        assert start_selector.selected_agents() == ("claude", "codex")
        claude_toggle = start_selector.query_one("#recipient-claude", AgentToggle)
        codex_toggle = start_selector.query_one("#recipient-codex", AgentToggle)
        assert claude_toggle.styles.width.value == 12
        assert codex_toggle.styles.width.value == 12
        assert claude_toggle.value is True
        assert codex_toggle.value is True
        assert start_selector.selected_model("codex") == "default"
        assert start_selector.model_option_labels("claude")[0] == "claude(default)"
        assert start_selector.model_option_labels("codex")[0] == "codex(default)"
        assert start_selector.query_one("#recipient-antigravity", AgentToggle).value is False
        assert start_selector.selected_model("antigravity") == "default"
        assert start_selector.model_option_labels("antigravity")[0] == "agy(default)"
        codex_toggle._toggle()
        assert start_selector.selected_agents() == ("claude",)

        app.switch_to("nexus")
        await pilot.pause()

        nexus_selector = app.screen.query_one(
            "#nexus-recipient-selector",
            AgentRecipientModelSelector,
        )
        assert nexus_selector.query_one(".recipient-label").styles.min_width.value == 4
        assert nexus_selector.selected_agents() == ("claude", "codex")
        assert nexus_selector.selected_model("claude") == "default"
        assert nexus_selector.query_one("#recipient-antigravity", AgentToggle).value is False


@pytest.mark.asyncio
async def test_agent_recipient_selector_accepts_live_model_choices(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents["codex"].enabled = True
    app = TrinityTextualApp(config, FakeWorkflowController())

    async with app.run_test(size=(120, 34)):
        selector = app.screen.query_one(
            "#start-recipient-selector",
            AgentRecipientModelSelector,
        )
        selector.set_model_choices(
            "codex",
            [
                ProviderModelChoice(
                    provider=Provider.CODEX,
                    model="default",
                    label="codex(default)",
                    source="static-fallback",
                    is_default=True,
                    context_budget=128_000,
                ),
                ProviderModelChoice(
                    provider=Provider.CODEX,
                    model="gpt-5.5",
                    label="gpt-5.5",
                    source="cli-live",
                    context_budget=None,
                ),
            ],
        )

        assert selector.model_option_labels("codex") == ("codex(default)", "gpt-5.5")
        selector.set_model_overrides({"codex": "gpt-5.5"})
        assert selector.model_overrides() == {"codex": "gpt-5.5"}


@pytest.mark.asyncio
async def test_model_slash_modal_updates_selector_model_override(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents["codex"].enabled = True
    config.agents["codex"].model = "default"
    controller = FakeWorkflowController()
    app = TrinityTextualApp(config, controller)
    app._start_model_discovery = lambda: None  # type: ignore[method-assign]
    app._refresh_provider_models = lambda *, use_cache: None  # type: ignore[method-assign]

    async with app.run_test(size=(120, 34)) as pilot:
        selector = app.screen.query_one(
            "#start-recipient-selector",
            AgentRecipientModelSelector,
        )
        selector.set_model_choices(
            "codex",
            [
                ProviderModelChoice(
                    provider=Provider.CODEX,
                    model="default",
                    label="codex(default)",
                    source="static-fallback",
                    is_default=True,
                    context_budget=128_000,
                ),
                ProviderModelChoice(
                    provider=Provider.CODEX,
                    model="gpt-5.5",
                    label="gpt-5.5",
                    source="cli-live",
                    context_budget=None,
                ),
            ],
        )

        app._handle_textual_slash_command("/model")
        await pilot.pause()

        assert isinstance(app.screen, ModelSettingsModal)
        app.screen.query_one("#model-agent-codex", Button).press()
        await pilot.pause()

        menu = app.screen.query_one("#model-choice-list", OptionList)
        labels = app.screen.choice_labels("codex")
        menu.highlighted = next(
            index for index, label in enumerate(labels) if "gpt-5.5" in label
        )
        menu.action_select()
        await pilot.pause()

        app.screen.query_one("#apply-model-settings", Button).press()
        await pilot.pause()

        assert selector.selected_model("codex") == "gpt-5.5"
        assert selector.model_overrides() == {"codex": "gpt-5.5"}

        composer = app.screen.query_one("#start-composer", PromptComposer)
        composer.set_text("코덱스 모델 확인")
        composer.action_submit()
        await pilot.pause()

        assert controller.started_models[-1] == {"codex": "gpt-5.5"}


def test_open_model_settings_unavailable_uses_korean_notification(
    tmp_path,
    monkeypatch,
) -> None:
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    )
    notifications: list[tuple[str, str, str]] = []
    monkeypatch.setattr(app, "_active_agent_selector", lambda: None)
    monkeypatch.setattr(
        app,
        "notify",
        lambda message, **kwargs: notifications.append(
            (message, str(kwargs.get("title", "")), str(kwargs.get("severity", "info")))
        ),
    )

    app._open_model_settings_modal()

    assert notifications == [
        (
            "모델 설정은 시작 화면과 Nexus에서 사용할 수 있습니다.",
            "모델 설정",
            "warning",
        )
    ]


def test_model_settings_applied_uses_korean_notification(tmp_path, monkeypatch) -> None:
    class FakeSelector:
        def __init__(self) -> None:
            self.selections: dict[str, str] = {}

        def set_model_selections(self, selections: dict[str, str]) -> None:
            self.selections = dict(selections)

    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    )
    selector = FakeSelector()
    notifications: list[tuple[str, str, str]] = []
    monkeypatch.setattr(app, "_active_agent_selector", lambda: selector)
    monkeypatch.setattr(
        app,
        "notify",
        lambda message, **kwargs: notifications.append(
            (message, str(kwargs.get("title", "")), str(kwargs.get("severity", "info")))
        ),
    )

    app._on_model_settings_applied({"codex": "gpt-5.5"})

    assert selector.selections == {"codex": "gpt-5.5"}
    assert notifications == [
        ("모델 설정을 업데이트했습니다.", "모델 설정", "info"),
    ]


def test_model_settings_modal_uses_korean_source_labels(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    config.agents["codex"].enabled = True
    modal = ModelSettingsModal(
        config.agents,
        {
            "codex": (
                ProviderModelChoice(
                    provider=Provider.CODEX,
                    model="gpt-5.5",
                    label="gpt-5.5",
                    source="cli-live",
                    context_budget=None,
                ),
            )
        },
        {"codex": "gpt-5.5"},
        lang="ko",
    )

    assert modal.choice_labels("codex") == ["gpt-5.5  CLI 실시간"]


@pytest.mark.asyncio
async def test_model_slash_refreshes_provider_models_without_cache(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(TrinityTextualApp, "_start_model_discovery", lambda self: None)
    config = TrinityConfig.default_config(project_dir=tmp_path)
    app = TrinityTextualApp(config, FakeWorkflowController())
    refreshes: list[bool] = []

    def refresh_provider_models(*, use_cache: bool) -> None:
        refreshes.append(use_cache)

    app._refresh_provider_models = refresh_provider_models  # type: ignore[method-assign]

    async with app.run_test(size=(120, 34)) as pilot:
        app._handle_textual_slash_command("/model")
        await pilot.pause()

        assert isinstance(app.screen, ModelSettingsModal)
        assert refreshes == [False]


@pytest.mark.asyncio
async def test_model_slash_modal_highlights_current_model_selection(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(TrinityTextualApp, "_start_model_discovery", lambda self: None)
    config = TrinityConfig.default_config(project_dir=tmp_path)
    app = TrinityTextualApp(config, FakeWorkflowController())
    app._refresh_provider_models = lambda *, use_cache: None  # type: ignore[method-assign]

    async with app.run_test(size=(120, 34)) as pilot:
        selector = app.screen.query_one(
            "#start-recipient-selector",
            AgentRecipientModelSelector,
        )
        selector.set_model_choices(
            "antigravity",
            [
                ProviderModelChoice(
                    provider=Provider.ANTIGRAVITY_CLI,
                    model="default",
                    label="agy(default)",
                    source="static-fallback",
                    is_default=True,
                    context_budget=1_000_000,
                ),
                ProviderModelChoice(
                    provider=Provider.ANTIGRAVITY_CLI,
                    model="Gemini 3.5 Flash (Medium)",
                    label="Gemini 3.5 Flash (Medium)",
                    source="cli-live",
                    context_budget=None,
                ),
                ProviderModelChoice(
                    provider=Provider.ANTIGRAVITY_CLI,
                    model="Gemini 3.1 Pro (High)",
                    label="Gemini 3.1 Pro (High)",
                    source="cli-live",
                    context_budget=None,
                ),
            ],
        )
        selector.set_model_selections({"antigravity": "Gemini 3.1 Pro (High)"})

        app._handle_textual_slash_command("/model")
        await pilot.pause()

        assert isinstance(app.screen, ModelSettingsModal)
        app.screen.query_one("#model-agent-antigravity", Button).press()
        await pilot.pause()

        menu = app.screen.query_one("#model-choice-list", OptionList)
        assert menu.highlighted == 2


@pytest.mark.asyncio
async def test_open_model_modal_receives_late_discovered_models(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents["codex"].enabled = True
    app = TrinityTextualApp(config, FakeWorkflowController())

    async with app.run_test(size=(120, 34)) as pilot:
        app._handle_textual_slash_command("/model")
        await pilot.pause()

        assert isinstance(app.screen, ModelSettingsModal)
        app.screen.query_one("#model-agent-codex", Button).press()
        await pilot.pause()
        assert "gpt-5.5" not in app.screen.choice_labels("codex")

        app._apply_discovered_model_choices(
            {
                "codex": (
                    ProviderModelChoice(
                        provider=Provider.CODEX,
                        model="default",
                        label="codex(default)",
                        source="static-fallback",
                        is_default=True,
                        context_budget=128_000,
                    ),
                    ProviderModelChoice(
                        provider=Provider.CODEX,
                        model="gpt-5.5",
                        label="gpt-5.5",
                        source="cli-live",
                        context_budget=None,
                    ),
                )
            }
        )
        await pilot.pause()

        assert "gpt-5.5  cli-live" in app.screen.choice_labels("codex")


@pytest.mark.asyncio
async def test_app_skips_unchanged_discovered_model_choice_sync(
    tmp_path,
    monkeypatch,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    app = TrinityTextualApp(config, FakeWorkflowController())
    app._model_discovery_started = True
    spec = config.agents["claude"]
    initial = (
        ProviderModelChoice(
            provider=spec.provider,
            model="default",
            label="claude(default)",
            source="static-fallback",
            is_default=True,
            context_budget=200_000,
        ),
    )
    updated = (
        *initial,
        ProviderModelChoice(
            provider=spec.provider,
            model="opus",
            label="opus",
            source="cli-live",
            context_budget=1_000_000,
        ),
    )

    async with app.run_test(size=(120, 34)) as pilot:
        await pilot.pause()
        app._apply_discovered_model_choices({"claude": initial})
        await pilot.pause()

        start = app.get_screen("start", StartScreen)
        nexus = app.get_screen("nexus", NexusScreen)
        settings = app.get_screen("settings", SettingsScreen)
        calls: list[tuple[str, dict[str, tuple[ProviderModelChoice, ...]]]] = []

        def counted_start(choices_by_agent) -> None:
            calls.append(("start", dict(choices_by_agent)))

        def counted_nexus(choices_by_agent) -> None:
            calls.append(("nexus", dict(choices_by_agent)))

        def counted_settings(choices_by_agent) -> None:
            calls.append(("settings", dict(choices_by_agent)))

        monkeypatch.setattr(start, "set_agent_model_choices", counted_start)
        monkeypatch.setattr(nexus, "set_agent_model_choices", counted_nexus)
        monkeypatch.setattr(settings, "set_agent_model_choices", counted_settings)

        app._apply_discovered_model_choices({"claude": tuple(initial)})
        await pilot.pause()
        assert calls == []

        app._apply_discovered_model_choices({"claude": updated})
        await pilot.pause()
        assert calls == [
            ("start", {"claude": updated}),
            ("nexus", {"claude": updated}),
            ("settings", {"claude": updated}),
        ]


@pytest.mark.asyncio
async def test_textual_app_switches_named_routes(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(100, 30)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        assert app.current_route == "nexus"
        assert app.screen.name == "nexus"

        app.switch_to("settings")
        await pilot.pause()
        assert app.current_route == "settings"
        assert app.screen.name == "settings"
        assert isinstance(app.screen, SettingsScreen)


@pytest.mark.asyncio
async def test_textual_app_switches_to_report_screen_without_render_crash(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(100, 30)) as pilot:
        app.switch_to("report")
        await pilot.pause()

        assert app.current_route == "report"
        assert app.screen.name == "report"
        assert isinstance(app.screen, ReportScreen)
        assert app.screen.query_one("#report-body")


@pytest.mark.asyncio
async def test_report_screen_uses_korean_chrome_labels(tmp_path) -> None:
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    )

    async with app.run_test(size=(100, 30)) as pilot:
        app.switch_to("report")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, ReportScreen)
        assert str(screen.query_one("#report-title", Static).content) == (
            "📋 워크플로우 리포트"
        )
        assert str(screen.query_one("#report-export-btn", Button).label) == (
            "💾 마크다운 내보내기"
        )
        assert _binding_description(
            screen._bindings, "ctrl+s", "export_report"
        ) == "마크다운 내보내기"
        assert _binding_description(screen._bindings, "escape", "go_back") == "뒤로"

        screen.show_export_path(tmp_path / "report-[/dim].md")
        await pilot.pause()

        status = screen.query_one("#report-export-status", Static)
        assert "저장됨:" in str(status.render())


@pytest.mark.asyncio
async def test_report_screen_snapshot_uses_korean_body_labels(tmp_path) -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-ko-report",
        goal="한국어 본문",
        state="blueprint_ready",
        synthesis=SynthesisSnapshot(
            summary="합의 요약",
            consensus_progress="blueprint ready",
            source="central",
        ),
        decisions=["결정 기록"],
        providers=[
            ProviderSnapshot(
                name="codex",
                provider="codex-cli",
                enabled=True,
                status="Ready",
                actual_model="gpt-5.5",
                context_window=272000,
                budget_source="local_cli_cache",
                session_id="019ea9e3-426f",
                profile_modes=["execute", "review"],
                context_profile="implementer",
                output_contract="execution_v1",
                profile_strengths=["implementation"],
            )
        ],
        agent_quality=[
            AgentQualitySnapshot(
                agent_name="codex",
                signal_count=3,
                success_count=2,
                blocker_count=1,
                required_change_count=4,
                score=0.667,
            ),
            AgentQualitySnapshot(
                agent_name="",
                signal_count=0,
                success_count=0,
                blocker_count=0,
                required_change_count=0,
                score=0.0,
            )
        ],
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Execution UI",
                owner_agent="codex",
                status="running",
                current_executor="codex",
                task_kind="implementation",
                routing_reason="implementation strength 0.95",
                routing_score=111.0,
                profile_revision="default-v1",
                parallel_group=1,
            ),
            WorkPackageSnapshot(
                id="WP-002",
                title="Serial fallback",
                owner_agent="claude",
                status="done",
                parallelizable=False,
                review_status="skipped",
                review_summary=(
                    "only claude is active; no non-owner peer reviewer is available"
                ),
            )
        ],
        questions=[
            QuestionSnapshot(
                id="q-1",
                question="계속할까요?",
                options=["예", "아니오"],
                recommended_option="예",
            )
        ],
        execution_recovery=ExecutionRecoverySnapshot(
            run_id="run-ko",
            state="interrupted",
            target_workspace="/tmp/project",
            running_packages=("WP-001",),
            retry_candidates=("WP-002",),
            done_packages=("WP-000",),
        ),
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        workflow_controller=FakeWorkflowController(snapshot),
    )
    app.active_snapshot = snapshot

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("report")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, ReportScreen)
        body = screen.query_one("#report-body")
        rendered = "\n".join(str(child.render()) for child in body.children)

    assert "개요" in rendered
    assert "세션" in rendered
    assert "목표" in rendered
    assert "프로바이더" in rendered
    assert "컨텍스트 272,000" in rendered
    assert "프로필 구현자" in rendered
    assert "자문 에이전트 품질" in rendered
    assert "점수 0.667" in rendered
    assert "변경 요청 4" in rendered
    assert "알 수 없음" in rendered
    assert "작업 패키지 라우팅" in rendered
    assert "상태 실행 중" in rendered
    assert "상태 완료" in rendered
    assert "소유자 codex" in rendered
    assert "종류 구현" in rendered
    assert "이유: 구현 강점 0.95" in rendered
    assert "그룹 직렬" in rendered
    assert (
        "리뷰 동료 없음/(없음); 이유 활성 에이전트가 claude뿐이라 "
        "동료 리뷰어가 없습니다."
    ) in rendered
    assert "실행 복구" in rendered
    assert "상태: 중단" in rendered
    assert "미해결 질문" in rendered
    assert "예 (추천)" in rendered


@pytest.mark.asyncio
async def test_report_screen_escapes_snapshot_markup(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(100, 30)) as pilot:
        app.active_snapshot = WorkflowNexusSnapshot(
            session_id="wf-[/bold]",
            goal="fix [/bold] crash",
            state="idle[/bold]",
            synthesis=SynthesisSnapshot(
                summary="summary [/bold]",
                consensus_progress="round [/bold]",
                source="shared[/bold]",
            ),
            decisions=["decision [/bold]"],
            work_packages=["WP [/bold]"],
            execution_log=["log [/bold]"],
            questions=[
                QuestionSnapshot(
                    id="q[/bold]",
                    question="question [/bold]",
                    options=["option [/bold]"],
                    recommended_option="option [/bold]",
                )
            ],
        )

        app.switch_to("report")
        await pilot.pause()

        assert isinstance(app.screen, ReportScreen)
        assert app.screen.query_one("#report-body")


@pytest.mark.asyncio
async def test_report_screen_rerenders_when_report_content_changes(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    def report_for(title: str):
        session = WorkflowSession(
            id="same-session",
            goal="same goal",
            state=WorkflowState.BLUEPRINT_READY,
            current_round=1,
            work_packages=[
                WorkPackage(
                    id="wp-1",
                    title=title,
                    owner_agent="codex",
                    objective="same objective",
                    status=WorkStatus.PENDING,
                ),
            ],
        )
        return DeliberationReportBuilder(session, result=None).build()

    async with app.run_test(size=(100, 30)) as pilot:
        app.switch_to("report")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, ReportScreen)

        screen.apply_report(report_for("First package"))
        await pilot.pause()
        body = screen.query_one("#report-body")
        first_render = "\n".join(str(child.render()) for child in body.children)
        assert "First package" in first_render

        screen.apply_report(report_for("Second package"))
        await pilot.pause()
        second_render = "\n".join(str(child.render()) for child in body.children)
        assert "Second package" in second_render
        assert "First package" not in second_render


@pytest.mark.asyncio
async def test_report_screen_escapes_export_status_path(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(100, 30)) as pilot:
        app.switch_to("report")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, ReportScreen)
        screen.show_export_path(tmp_path / "report-[/dim].md")
        await pilot.pause()

        status = screen.query_one("#report-export-status")
        assert "Saved:" in str(status.render())
        assert "report-" in str(status.render())


@pytest.mark.asyncio
async def test_report_screen_snapshot_shows_work_package_routing_metadata(
    tmp_path,
) -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-routing",
        goal="route work",
        state="blueprint_ready",
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Execution UI",
                owner_agent="codex",
                status="running",
                current_executor="codex",
                task_kind="implementation",
                routing_reason="implementation strength 0.95",
                routing_score=111.0,
                profile_revision="default-v1",
                parallel_group=1,
            ),
            WorkPackageSnapshot(
                id="WP-002",
                title="Single provider review",
                owner_agent="codex",
                status="done",
                review_status="skipped",
                review_summary=(
                    "only codex is active; no non-owner peer reviewer is available"
                ),
            ),
        ],
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path),
        workflow_controller=FakeWorkflowController(snapshot),
    )
    app.active_snapshot = snapshot

    async with app.run_test(size=(100, 30)) as pilot:
        app.switch_to("report")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, ReportScreen)
        body = screen.query_one("#report-body")
        rendered = "\n".join(str(child.render()) for child in body.children)

    assert "Work Package Routing" in rendered
    assert "WP-001" in rendered
    assert "kind implementation" in rendered
    assert "profile default-v1" in rendered
    assert "reason: implementation strength 0.95" in rendered
    assert "review no peer/(none)" in rendered
    assert "no non-owner peer reviewer is available" in rendered


@pytest.mark.asyncio
async def test_textual_export_uses_snapshot_when_session_is_not_persisted(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-memory-only",
        goal="memory only report",
        state="preflight",
        synthesis=SynthesisSnapshot(
            summary="snapshot summary",
            consensus_progress="in progress",
            source="memory",
        ),
        decisions=["use snapshot fallback"],
        work_packages=["wp-1 codex: implement fallback (pending)"],
        execution_log=["no execution yet"],
    )

    async with app.run_test(size=(100, 30)):
        app._export_report_markdown(snapshot)

    reports = list((app.config.effective_state_dir / "reports").glob("report-*.md"))
    assert len(reports) == 1
    md = reports[0].read_text(encoding="utf-8")
    assert "memory only report" in md
    assert "snapshot summary" in md
    assert "use snapshot fallback" in md


@pytest.mark.asyncio
async def test_textual_export_snapshot_uses_korean_markdown_labels(
    tmp_path,
    monkeypatch,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    app = TrinityTextualApp(config)
    notifications: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        app,
        "notify",
        lambda message, **kwargs: notifications.append(
            (message, str(kwargs.get("title", "")), str(kwargs.get("severity", "info")))
        ),
    )
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-ko",
        goal="한국어 리포트",
        state="preflight",
        decisions=["스냅샷 fallback 사용"],
    )

    async with app.run_test(size=(100, 30)):
        app._export_report_markdown(snapshot)

    reports = list((app.config.effective_state_dir / "reports").glob("report-*.md"))
    assert len(reports) == 1
    md = reports[0].read_text(encoding="utf-8")
    assert "# 워크플로우 리포트" in md
    assert "**목표**: 한국어 리포트" in md
    assert "## 결정" in md
    assert notifications == [
        (f"리포트 저장됨: {reports[0]}", "내보내기 완료", "info"),
    ]


@pytest.mark.asyncio
async def test_textual_export_uses_persisted_session_when_available(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="persisted-session",
            goal="persisted report",
            state=WorkflowState.BLUEPRINT_READY,
            work_packages=[
                WorkPackage(
                    id="wp-persisted",
                    title="Persisted package",
                    owner_agent="codex",
                    objective="export from persisted workflow",
                    status=WorkStatus.PENDING,
                )
            ],
        )
    )
    persistence.append_event(
        {
            "timestamp": 1781136000.0,
            "workflow_id": "persisted-session",
            "event": "central_conversation_recorded",
            "state": "blueprint_ready",
            "data": {
                "role": "central",
                "channel": "nexus",
                "title": "Central Agent Response",
                "body": "Persisted central transcript",
            },
        }
    )
    persistence.append_event(
        {
            "timestamp": 1781136060.0,
            "workflow_id": "persisted-session",
            "event": "execution_run_started",
            "state": "executing",
            "data": {
                "run_id": "exec-run-persisted",
                "target_workspace": str(tmp_path),
                "work_packages": ["wp-persisted"],
            },
        }
    )
    app = TrinityTextualApp(config, workflow_controller=FakeWorkflowController())

    async with app.run_test(size=(100, 30)) as pilot:
        app.switch_to("report")
        await pilot.pause()
        app._export_report_markdown(WorkflowNexusSnapshot(session_id="persisted-session"))
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, ReportScreen)
        status = screen.query_one("#report-export-status")
        assert "Saved:" in str(status.render())

    reports = list((config.effective_state_dir / "reports").glob("report-*.md"))
    assert len(reports) == 1
    md = reports[0].read_text(encoding="utf-8")
    assert "persisted report" in md
    assert "wp-persisted" in md
    assert "export from persisted workflow" in md
    assert "## Central Agent Conversation" in md
    assert "Persisted central transcript" in md
    assert "## Execution Timeline" in md
    assert "exec-run-persisted" in md


@pytest.mark.asyncio
async def test_report_screen_bounds_events_but_export_uses_full_history(
    tmp_path,
    monkeypatch,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="bounded-report-session",
            goal="bounded report",
            state=WorkflowState.BLUEPRINT_READY,
            current_round=1,
        )
    )
    for index, body in enumerate(
        (
            "oldest persisted transcript",
            "middle persisted transcript",
            "latest persisted transcript",
        )
    ):
        persistence.append_event(
            {
                "timestamp": 1781136000.0 + index,
                "workflow_id": "bounded-report-session",
                "event": "central_conversation_recorded",
                "state": "blueprint_ready",
                "data": {
                    "role": "central",
                    "channel": "nexus",
                    "title": "Central Agent Response",
                    "body": body,
                },
            }
        )

    original_load_events = WorkflowPersistence.load_events_for_workflow
    load_tails: list[int | None] = []

    def record_load_events(
        self,
        workflow_id: str,
        *,
        tail: int | None = None,
        event_names=None,
    ):
        load_tails.append(tail)
        return original_load_events(
            self,
            workflow_id,
            tail=tail,
            event_names=event_names,
        )

    monkeypatch.setattr(textual_app_module, "WORKFLOW_EVENT_DISPLAY_LIMIT", 2)
    monkeypatch.setattr(
        WorkflowPersistence,
        "load_events_for_workflow",
        record_load_events,
    )

    app = TrinityTextualApp(config, workflow_controller=FakeWorkflowController())

    async with app.run_test(size=(100, 30)) as pilot:
        app.switch_to("report")
        await pilot.pause()
        assert load_tails == [2]

        screen = app.screen
        assert isinstance(screen, ReportScreen)
        body = screen.query_one("#report-body")
        rendered = "\n".join(str(child.render()) for child in body.children)
        assert "latest persisted transcript" in rendered

        app._export_report_markdown(
            WorkflowNexusSnapshot(session_id="bounded-report-session")
        )
        await pilot.pause()

    assert load_tails == [2, None]
    reports = list((config.effective_state_dir / "reports").glob("report-*.md"))
    assert len(reports) == 1
    md = reports[0].read_text(encoding="utf-8")
    assert "oldest persisted transcript" in md
    assert "latest persisted transcript" in md


@pytest.mark.asyncio
async def test_textual_export_empty_snapshot_does_not_create_report(
    tmp_path,
    monkeypatch,
) -> None:
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    )
    notifications: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        app,
        "notify",
        lambda message, **kwargs: notifications.append(
            (message, str(kwargs.get("title", "")), str(kwargs.get("severity", "info")))
        ),
    )

    async with app.run_test(size=(100, 30)):
        app._export_report_markdown(WorkflowNexusSnapshot())

    report_dir = app.config.effective_state_dir / "reports"
    assert not list(report_dir.glob("report-*.md"))
    assert notifications == [
        ("내보낼 워크플로우 데이터가 없습니다.", "내보내기 불가", "warning"),
    ]


def test_snapshot_report_markdown_escapes_user_markdown() -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-#1",
        goal="# injected heading",
        state="idle",
        synthesis=SynthesisSnapshot(
            summary="# summary heading\n- summary item",
            consensus_progress="- progress",
            source="[source](url)",
        ),
        decisions=["- injected list", "**bold** decision"],
        work_packages=["wp | table"],
        execution_log=["log # heading"],
        questions=[
            QuestionSnapshot(
                id="q#1",
                question="- choose me",
            )
        ],
    )

    md = snapshot_report_markdown(snapshot)

    assert "**Goal**: \\# injected heading" in md
    assert "**Progress**: \\- progress" in md
    assert "**Source**: \\[source\\]\\(url\\)" in md
    assert "- \\- injected list" in md
    assert "- \\*\\*bold\\*\\* decision" in md
    assert "- wp \\| table" in md
    assert "- **q\\#1**: \\- choose me" in md
    assert "```\n# summary heading\n- summary item\n```" in md


def test_snapshot_report_markdown_includes_provider_metadata() -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-provider",
        goal="design",
        state="blueprint_ready",
        providers=[
            ProviderSnapshot(
                name="codex",
                provider="codex · gpt-5.5",
                enabled=True,
                status="Ready",
                configured_model="default",
                actual_model="gpt-5.5",
                context_window=272000,
                budget_source="local_cli_cache",
                session_id="019ea9e3-426f",
                profile_mission="Implement and test approved work packages",
                profile_modes=["execute", "review"],
                profile_strengths=[
                    "implementation",
                    "testing",
                    "repair",
                    "integration",
                ],
                context_profile="implementer",
                output_contract="execution_v1",
            )
        ],
    )

    md = snapshot_report_markdown(snapshot)

    assert "## Providers" in md
    assert "**codex**: gpt\\-5\\.5; context 272,000 (local\\_cli\\_cache)" in md
    assert "session 019ea9e3\\-426" in md
    assert "profile implementer" in md
    assert "modes execute, review" in md
    assert "output execution\\_v1" in md
    assert "strengths implementation, testing, repair, \\+1" in md
    assert "mission Implement and test approved work packages" in md


def test_snapshot_report_markdown_includes_agent_quality_metadata() -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-quality",
        goal="quality report",
        state="reviewing",
        agent_quality=[
            AgentQualitySnapshot(
                agent_name="codex",
                signal_count=3,
                success_count=2,
                blocker_count=1,
                required_change_count=4,
                score=0.667,
            )
        ],
    )

    md = snapshot_report_markdown(snapshot)

    assert "## Advisory Agent Quality" in md
    assert "**codex**: score 0\\.667; success 2/3" in md
    assert "blockers 1; required changes 4" in md


def test_snapshot_report_markdown_localizes_korean_consensus_progress() -> None:
    markdown = snapshot_report_markdown(
        WorkflowNexusSnapshot(
            synthesis=SynthesisSnapshot(
                summary="중앙 에이전트가 응답을 종합 중입니다.",
                consensus_progress="round 1 synthesizing",
                source="runtime",
            )
        ),
        lang="ko",
    )

    assert "**진행**: 1라운드 종합 중" in markdown
    assert "**출처**: 런타임" in markdown
    assert "round 1 synthesizing" not in markdown


@pytest.mark.asyncio
async def test_report_screen_snapshot_shows_provider_profile_metadata(
    tmp_path,
) -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-provider",
        goal="route work",
        state="blueprint_ready",
        providers=[
            ProviderSnapshot(
                name="codex",
                provider="codex",
                enabled=True,
                status="Ready",
                actual_model="gpt-5.5",
                context_window=272000,
                budget_source="local_cli_cache",
                session_id="019ea9e3-426f",
                profile_modes=["execute", "review"],
                context_profile="implementer",
                output_contract="execution_v1",
            )
        ],
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path),
        workflow_controller=FakeWorkflowController(snapshot),
    )
    app.active_snapshot = snapshot

    async with app.run_test(size=(100, 30)) as pilot:
        app.switch_to("report")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, ReportScreen)
        body = screen.query_one("#report-body")
        rendered = "\n".join(str(child.render()) for child in body.children)

    assert "Providers" in rendered
    assert "codex" in rendered
    assert "profile implementer" in rendered
    assert "modes execute, review" in rendered
    assert "output execution_v1" in rendered


@pytest.mark.asyncio
async def test_report_screen_snapshot_shows_agent_quality_metadata(
    tmp_path,
) -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-quality",
        goal="quality report",
        state="reviewing",
        agent_quality=[
            AgentQualitySnapshot(
                agent_name="codex",
                signal_count=3,
                success_count=2,
                blocker_count=1,
                required_change_count=4,
                score=0.667,
            )
        ],
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path),
        workflow_controller=FakeWorkflowController(snapshot),
    )
    app.active_snapshot = snapshot

    async with app.run_test(size=(100, 30)) as pilot:
        app.switch_to("report")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, ReportScreen)
        body = screen.query_one("#report-body")
        rendered = "\n".join(str(child.render()) for child in body.children)

    assert "Advisory Agent Quality" in rendered
    assert "codex" in rendered
    assert "score 0.667" in rendered
    assert "success 2/3" in rendered
    assert "required changes 4" in rendered


def test_snapshot_report_markdown_includes_work_package_routing_metadata() -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-routing",
        goal="ship feature",
        state="blueprint_ready",
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Execution UI",
                owner_agent="codex",
                status="done",
                last_executor="claude",
                task_kind="implementation",
                routing_reason="implementation strength 0.95",
                routing_score=111.0,
                profile_revision="default-v1",
                parallel_group=2,
                review_status="approved",
                reviewer_agent="antigravity",
            ),
            WorkPackageSnapshot(
                id="WP-002",
                title="Single provider review",
                owner_agent="codex",
                status="done",
                review_status="skipped",
                review_summary=(
                    "only codex is active; no non-owner peer reviewer is available"
                ),
            ),
        ],
    )

    md = snapshot_report_markdown(snapshot)

    assert "## Work Package Routing" in md
    assert "**WP\\-001** Execution UI" in md
    assert "owner codex; executor claude; lane g2" in md
    assert "Routing: kind implementation; profile default\\-v1; score 111" in md
    assert "Reason: implementation strength 0\\.95" in md
    assert "Review: approved; reviewer antigravity" in md
    assert (
        "Review: no peer; reviewer \\(none\\); reason only codex is active; "
        "no non\\-owner peer reviewer is available"
    ) in md


def test_snapshot_report_markdown_uses_korean_labels() -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-ko",
        goal="한국어 리포트",
        state="blueprint_ready",
        round_num=2,
        providers=[
            ProviderSnapshot(
                name="codex",
                provider="codex",
                enabled=True,
                status="Ready",
                actual_model="gpt-5.5",
                context_window=1000,
                budget_source="runtime",
                session_id="session-123456",
                profile_mission="Implement work",
                profile_modes=["execute", "review"],
                profile_strengths=[
                    "implementation",
                    "testing",
                    "repair",
                    "integration",
                ],
                context_profile="implementer",
                output_contract="execution_v1",
            )
        ],
        agent_quality=[
            AgentQualitySnapshot(
                agent_name="codex",
                signal_count=3,
                success_count=2,
                blocker_count=1,
                required_change_count=4,
                score=0.667,
            )
        ],
        synthesis=SynthesisSnapshot(
            summary="요약",
            consensus_progress="진행중",
            source="shared",
        ),
        decisions=["결정 A"],
        central_work_packages=["WP-001 central"],
        work_packages=["WP-002 local"],
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="클라이언트",
                owner_agent="codex",
                status="done",
                current_executor="codex",
                parallelizable=False,
                task_kind="implementation",
                profile_revision="default-v1",
                routing_score=0.95,
                routing_reason="implementation strength",
                review_status="skipped",
                review_summary=(
                    "only codex is active; no non-owner peer reviewer is available"
                ),
            )
        ],
        execution_log=["event-1"],
        execution_recovery=ExecutionRecoverySnapshot(
            run_id="run-1",
            state="interrupted",
            target_workspace="/tmp/project",
            running_packages=("WP-001",),
            retry_candidates=("WP-001",),
            done_packages=("WP-000",),
            last_event="agent failed",
        ),
        questions=[QuestionSnapshot(id="q1", question="질문?")],
    )

    md = snapshot_report_markdown(snapshot, lang="ko")

    assert "# 워크플로우 리포트" in md
    assert "**세션**: wf\\-ko" in md
    assert "## 프로바이더" in md
    assert "컨텍스트 1,000 (런타임)" in md
    assert "세션 session\\-1234" in md
    assert "프로필 구현자" in md
    assert "모드 실행, 리뷰" in md
    assert "출력 실행 v1" in md
    assert "강점 구현, 테스트, 복구, \\+1" in md
    assert "## 자문 에이전트 품질" in md
    assert "점수 0\\.667; 성공 2/3; 차단 1; 변경 요청 4" in md
    assert "## 합의" in md
    assert "**진행**: 진행중" in md
    assert "**출처**: 공유 컨텍스트" in md
    assert "## 작업 패키지 라우팅" in md
    assert "상태: 완료; 소유자 codex; 실행자 codex; 그룹 직렬" in md
    assert "라우팅: 종류 구현; 프로필 default\\-v1; 점수 0\\.95" in md
    assert "이유: 구현 강점" in md
    assert (
        "리뷰: 동료 없음; 리뷰어 \\(없음\\); 이유 활성 에이전트가 codex뿐이라 "
        "동료 리뷰어가 없습니다\\."
    ) in md
    assert "## 실행 로그" in md
    assert "## 실행 복구" in md
    assert "- 실행: 중단" in md
    assert "## 미해결 질문" in md


def test_snapshot_report_markdown_localizes_korean_generic_review_skip_summary() -> None:
    snapshot = WorkflowNexusSnapshot(
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="리뷰 생략",
                owner_agent="codex",
                status="done",
                review_status="skipped",
                review_summary="Peer review skipped.",
            )
        ],
    )

    md = snapshot_report_markdown(snapshot, lang="ko")

    assert "이유 동료 리뷰가 생략되었습니다\\." in md
    assert "Peer review skipped" not in md


def test_snapshot_report_markdown_uses_korean_placeholder_values() -> None:
    snapshot = WorkflowNexusSnapshot(
        providers=[
            ProviderSnapshot(
                name="codex",
                provider="codex",
                enabled=True,
                status="",
            )
        ],
        agent_quality=[AgentQualitySnapshot(agent_name="")],
        work_package_details=[
            WorkPackageSnapshot(
                id="",
                title="",
                owner_agent="",
                status="",
            )
        ],
        execution_recovery=ExecutionRecoverySnapshot(),
    )

    md = snapshot_report_markdown(snapshot, lang="ko")

    assert "**세션**: \\(없음\\)" in md
    assert "**목표**: \\(없음\\)" in md
    assert "컨텍스트 \\(알 수 없음\\) (\\(알 수 없음\\)); 세션 \\(없음\\)" in md
    assert "- **\\(알 수 없음\\)**: 점수 0; 성공 0/0; 차단 0; 변경 요청 0" in md
    assert "- **\\(이름 없음\\)** \\(제목 없음\\)" in md
    assert "상태: \\(알 수 없음\\); 소유자 \\(알 수 없음\\); 실행자 \\(없음\\)" in md
    assert "- 실행 ID: \\(알 수 없음\\)" in md
    assert "- 대상: \\(미설정\\)" in md
    assert "- 실행 중 작업 패키지: \\(없음\\)" in md
    assert "- 재시도 후보: \\(없음\\)" in md
    assert "- 완료 작업 패키지: \\(없음\\)" in md
    assert "- 최근 이벤트: \\(없음\\)" in md


def test_snapshot_adapter_localizes_korean_central_blueprint_labels(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-blueprint-ko",
            goal="설계안 확인",
            state=WorkflowState.BLUEPRINT_READY,
            blueprint=Blueprint(
                title="Snake Game",
                summary="Build the game.",
                architecture=[
                    ArchitectureComponent(
                        name="Game Loop",
                        responsibility="Render and update.",
                        owner_agent="codex",
                        dependencies=["Canvas"],
                    )
                ],
                data_flow=["Input -> State -> Render"],
                external_dependencies=["pygame"],
                risks=[
                    RiskItem(
                        description="Frame drops",
                        severity="high",
                        mitigation="Profile rendering",
                        owner_agent="claude",
                    )
                ],
                acceptance_criteria=["Runs smoothly"],
                open_questions=[
                    OpenQuestion(
                        id="q1",
                        question="Grid size?",
                        options=["20x20", "30x30"],
                        recommended_option="20x20",
                    )
                ],
            ),
        )
    )

    markdown = NexusSnapshotAdapter(config).load_snapshot().central_blueprint

    assert "#### 아키텍처" in markdown
    assert "의존성: Canvas." in markdown
    assert "#### 데이터 흐름" in markdown
    assert "#### 외부 의존성" in markdown
    assert "#### 리스크" in markdown
    assert "완화: Profile rendering" in markdown
    assert "#### 인수 기준" in markdown
    assert "#### 미해결 질문" in markdown
    assert "선택지: 20x20, 30x30." in markdown
    assert "추천: 20x20." in markdown
    assert "#### Architecture" not in markdown
    assert "Dependencies:" not in markdown
    assert "Recommended:" not in markdown


def test_snapshot_adapter_keeps_english_central_blueprint_labels(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-blueprint-en",
            goal="check blueprint",
            state=WorkflowState.BLUEPRINT_READY,
            blueprint=Blueprint(
                title="Snake Game",
                summary="Build the game.",
                architecture=[
                    ArchitectureComponent(
                        name="Game Loop",
                        responsibility="Render and update.",
                        owner_agent="codex",
                        dependencies=["Canvas"],
                    )
                ],
                data_flow=["Input -> State -> Render"],
                external_dependencies=["pygame"],
                risks=[
                    RiskItem(
                        description="Frame drops",
                        severity="high",
                        mitigation="Profile rendering",
                        owner_agent="claude",
                    )
                ],
                acceptance_criteria=["Runs smoothly"],
                open_questions=[
                    OpenQuestion(
                        id="q1",
                        question="Grid size?",
                        options=["20x20", "30x30"],
                        recommended_option="20x20",
                    )
                ],
            ),
        )
    )

    markdown = NexusSnapshotAdapter(config).load_snapshot().central_blueprint

    assert "#### Architecture" in markdown
    assert "Dependencies: Canvas." in markdown
    assert "#### Data Flow" in markdown
    assert "#### External Dependencies" in markdown
    assert "#### Risks" in markdown
    assert "Mitigation: Profile rendering" in markdown
    assert "#### Acceptance Criteria" in markdown
    assert "#### Open Questions" in markdown
    assert "Options: 20x20, 30x30." in markdown
    assert "Recommended: 20x20." in markdown


def test_central_agent_view_localizes_korean_status_values() -> None:
    view = CentralAgentView(lang="ko")
    view.snapshot = WorkflowNexusSnapshot(
        state="post_review_ready",
        final_review=ReviewSnapshot(
            status="approved",
            reviewer_agent="codex",
            summary="Looks good.",
        ),
        post_review_items=[
            PostReviewActionSnapshot(
                id="AI-001",
                severity="high",
                status="pending",
                title="Add smoke test",
            ),
            PostReviewActionSnapshot(
                id="AI-002",
                severity="low",
                status="done",
                title="Update docs",
            ),
        ],
    )

    markdown = view.render_markdown()

    assert "- `승인` / 리뷰어 `codex`" in markdown
    assert "- **AI-001** [높음][대기] Add smoke test" in markdown
    assert "- **AI-002** [낮음][완료] Update docs" in markdown
    assert "`approved`" not in markdown
    assert "[pending]" not in markdown

    view.snapshot = WorkflowNexusSnapshot(
        state="post_review_ready",
        final_review=ReviewSnapshot(
            status="approved",
            reviewer_agent="",
        ),
    )

    assert "- `승인` / 리뷰어 `(알 수 없음)`" in view.render_markdown()


def test_central_agent_view_keeps_english_status_values() -> None:
    view = CentralAgentView()
    view.snapshot = WorkflowNexusSnapshot(
        state="post_review_ready",
        final_review=ReviewSnapshot(
            status="approved",
            reviewer_agent="codex",
        ),
        post_review_items=[
            PostReviewActionSnapshot(
                id="AI-001",
                severity="high",
                status="pending",
                title="Add smoke test",
            )
        ],
    )

    markdown = view.render_markdown()

    assert "- `approved` by `codex`" in markdown
    assert "- **AI-001** [high][pending] Add smoke test" in markdown


def test_central_agent_view_localizes_korean_guidance_labels() -> None:
    view = CentralAgentView(lang="ko")
    view.snapshot = WorkflowNexusSnapshot(
        local_commands=[
            LocalCommandSnapshot(
                command="/questions",
                title="질문",
                body="대기 중인 질문이 있습니다.",
                action_hint="질문 패널 버튼을 사용하세요.",
            )
        ]
    )

    command_markdown = view.render_markdown()

    assert "_다음:_ 질문 패널 버튼을 사용하세요." in command_markdown
    assert "_Next:_" not in command_markdown

    view.snapshot = WorkflowNexusSnapshot(
        state="post_review_ready",
        post_review_items=[
            PostReviewActionSnapshot(
                id="AI-001",
                severity="high",
                status="pending",
                title="테스트 보강",
            )
        ],
    )

    follow_up_markdown = view.render_markdown()

    assert (
        "`/improve high`, `/improve all`, `/improve AI-001`, "
        "`/improve done` 중 하나를 실행하세요."
    ) in follow_up_markdown
    assert "Use `/improve" not in follow_up_markdown

    view.snapshot = WorkflowNexusSnapshot(state="post_review_ready")

    done_markdown = view.render_markdown()

    assert "`/improve done`으로 워크플로우를 종료하세요." in done_markdown
    assert "Use `/improve done`" not in done_markdown


def test_central_agent_view_localizes_korean_review_repair_action_labels() -> None:
    view = CentralAgentView(lang="ko")

    assert view.label("details_in_inspector") == (
        "상세 설계와 작업 패키지 목록은 인스펙터 또는 리포트에서 확인하세요."
    )
    assert view.label("execution_retry") == "실패 작업 재시도"
    assert view.label("execute_tooltip") == "현재 작업 패키지를 실행합니다."
    assert view.label("execution-retry_tooltip") == (
        "실패, 막힘, 중단 상태의 작업 패키지를 선택해서 다시 실행합니다."
    )
    assert view.label("repair_action") == "리뷰 보정 결정"
    assert view.label("repair-retry-once_tooltip") == (
        "리뷰 보정으로 막힌 작업 패키지만 한 번 더 실행합니다."
    )
    assert view.label("repair-mark-done_tooltip") == (
        "막힌 리뷰 보정을 사용자가 수용하고 작업 패키지를 완료 처리합니다."
    )
    assert view.label("repair-open-review_tooltip") == (
        "현재 리뷰 보정 차단 상세를 봅니다."
    )


def test_central_agent_view_localizes_korean_execution_progress() -> None:
    view = CentralAgentView(lang="ko")
    snapshot = WorkflowNexusSnapshot(
        state="executing",
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Done",
                owner_agent="codex",
                status="done",
            ),
            WorkPackageSnapshot(
                id="WP-002",
                title="Run",
                owner_agent="codex",
                status="running",
            ),
            WorkPackageSnapshot(
                id="WP-003",
                title="Wait",
                owner_agent="codex",
                status="pending",
            ),
            WorkPackageSnapshot(
                id="WP-004",
                title="Blocked",
                owner_agent="codex",
                status="blocked",
            ),
        ],
    )

    assert view.execution_progress(snapshot) == (
        "실행 중: 1 완료 / 1 실행 중 / 1 대기 / 1 막힘"
    )


def test_central_agent_view_keeps_english_execution_progress() -> None:
    view = CentralAgentView()
    snapshot = WorkflowNexusSnapshot(
        state="executing",
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Done",
                owner_agent="codex",
                status="done",
            ),
            WorkPackageSnapshot(
                id="WP-002",
                title="Run",
                owner_agent="codex",
                status="running",
            ),
            WorkPackageSnapshot(
                id="WP-003",
                title="Wait",
                owner_agent="codex",
                status="pending",
            ),
        ],
    )

    assert view.execution_progress(snapshot) == (
        "Executing: 1 done / 1 running / 1 waiting"
    )


def test_unique_report_path_avoids_existing_file_and_sanitizes_session_id(
    tmp_path,
) -> None:
    report_dir = tmp_path / "reports"
    first = unique_report_path(report_dir, "wf/unsafe")
    first.write_text("existing", encoding="utf-8")

    second = unique_report_path(report_dir, "wf/unsafe")

    assert second != first
    assert "/" not in second.name
    assert second.name.startswith("report-wf-unsaf")


@pytest.mark.asyncio
async def test_start_screen_submission_moves_to_nexus(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path),
        controller,
    )

    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)

        composer = screen.query_one(PromptComposer)
        composer.set_text("설계해줘")
        composer.action_submit()
        await pilot.pause()

        assert app.initial_prompt == "설계해줘"
        assert app.current_route == "nexus"
        assert app.screen.name == "nexus"
        assert isinstance(app.screen, NexusScreen)
        assert app.screen.initial_prompt == "설계해줘"
        assert controller.started_prompts == ["설계해줘"]
        assert app.screen.snapshot is not None
        assert app.screen.snapshot.state == "deliberating"


@pytest.mark.asyncio
async def test_start_screen_defaults_target_workspace_to_launch_cwd(tmp_path) -> None:
    controller = FakeWorkflowController()
    control_repo = tmp_path / "control"
    launch_cwd = tmp_path / "target-app"
    control_repo.mkdir()
    launch_cwd.mkdir()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=control_repo),
        controller,
        launch_cwd=launch_cwd,
    )

    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)
        assert app.workspace_candidate == launch_cwd.resolve()
        assert str(launch_cwd.resolve()) in str(
            screen.query_one("#workspace-candidate").content
        )

        composer = screen.query_one(PromptComposer)
        composer.set_text("현재 폴더에서 작업해줘")
        composer.action_submit()
        await pilot.pause()

        assert controller.target_workspace == launch_cwd.resolve()
        assert app.confirmed_preflight is not None
        assert app.confirmed_preflight.path == launch_cwd.resolve()
        assert load_project_intake(app.config.effective_state_dir) is None

        app.action_go_execution()
        await pilot.pause()

        execution = app.screen
        assert isinstance(execution, ExecutionMatrixScreen)
        assert str(launch_cwd.resolve()) in str(
            execution.query_one("#execution-header").content
        )


@pytest.mark.asyncio
async def test_start_screen_does_not_prefer_project_intake_target_workspace(
    tmp_path,
) -> None:
    controller = FakeWorkflowController()
    control_repo = tmp_path / "control"
    launch_cwd = control_repo
    target_workspace = tmp_path / "customer-app"
    control_repo.mkdir()
    target_workspace.mkdir()
    config = TrinityConfig.default_config(project_dir=control_repo)
    write_project_intake(
        config.effective_state_dir,
        build_project_intake(
            mode="existing",
            target_workspace=target_workspace,
            created_at="2026-06-28T00:00:00Z",
        ),
    )
    app = TrinityTextualApp(config, controller, launch_cwd=launch_cwd)

    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)
        assert app.workspace_candidate == control_repo.resolve()
        assert str(control_repo.resolve()) in str(
            screen.query_one("#workspace-candidate").content
        )

        composer = screen.query_one(PromptComposer)
        composer.set_text("저장된 프로젝트를 분석해줘")
        composer.action_submit()
        await pilot.pause()

        assert controller.target_workspace is None
        assert app.confirmed_preflight is None


def test_initial_workspace_candidate_keeps_control_repo_launch_cwd(
    tmp_path,
) -> None:
    control_repo = tmp_path / "control"
    control_repo.mkdir()

    assert initial_workspace_candidate(control_repo) == control_repo


def test_initial_workspace_candidate_prefers_distinct_launch_cwd(
    tmp_path,
) -> None:
    control_repo = tmp_path / "control"
    launch_cwd = tmp_path / "launch-app"
    control_repo.mkdir()
    launch_cwd.mkdir()

    assert initial_workspace_candidate(launch_cwd) == launch_cwd


@pytest.mark.asyncio
async def test_start_screen_does_not_seed_composer_from_project_goal(tmp_path) -> None:
    controller = FakeWorkflowController()
    control_repo = tmp_path / "control"
    target_workspace = tmp_path / "customer-app"
    control_repo.mkdir()
    target_workspace.mkdir()
    config = TrinityConfig.default_config(project_dir=control_repo)
    write_project_intake(
        config.effective_state_dir,
        build_project_intake(
            mode="new",
            target_workspace=target_workspace,
            product_goal="Build customer onboarding.",
            created_at="2026-06-28T00:00:00Z",
        ),
    )
    app = TrinityTextualApp(config, controller, launch_cwd=control_repo)

    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)
        composer = screen.query_one(PromptComposer)

        assert composer.text == ""
        assert str(control_repo.resolve()) in str(
            screen.query_one("#workspace-candidate").content
        )

        composer.set_text("사용자 프롬프트만 실행해라")
        composer.action_submit()
        await pilot.pause()

        assert controller.target_workspace is None
        assert controller.started_prompts[-1] == "사용자 프롬프트만 실행해라"


@pytest.mark.asyncio
async def test_start_screen_launch_cwd_inside_control_repo_stays_unconfirmed(
    tmp_path,
) -> None:
    controller = FakeWorkflowController()
    control_repo = tmp_path / "control"
    control_repo.mkdir()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=control_repo),
        controller,
        launch_cwd=control_repo,
    )

    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)
        assert str(control_repo.resolve()) in str(
            screen.query_one("#workspace-candidate").content
        )

        composer = screen.query_one(PromptComposer)
        composer.set_text("컨트롤 repo 내부 기본값은 확인 전까지 저장하지 마")
        composer.action_submit()
        await pilot.pause()

        assert controller.target_workspace is None
        assert app.confirmed_preflight is None


@pytest.mark.asyncio
async def test_start_submission_passes_selected_agents_and_models(tmp_path) -> None:
    controller = FakeWorkflowController()
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents["codex"].enabled = True
    app = TrinityTextualApp(config, controller)

    async with app.run_test(size=(120, 34)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)
        selector = screen.query_one(AgentRecipientModelSelector)
        selector.set_selected_agents(("codex",))
        selector.set_model_overrides({"codex": "gpt-5"})

        composer = screen.query_one(PromptComposer)
        composer.set_text("코덱스에게만 물어봐")
        composer.action_submit()
        await pilot.pause()

        assert controller.started_prompts == ["코덱스에게만 물어봐"]
        assert controller.started_targets == [("codex",)]
        assert controller.started_models[-1]["codex"] == "gpt-5"
        assert isinstance(app.screen, NexusScreen)
        nexus_selector = app.screen.query_one(AgentRecipientModelSelector)
        assert nexus_selector.selected_agents() == ("codex",)
        assert nexus_selector.model_overrides()["codex"] == "gpt-5"


@pytest.mark.asyncio
async def test_start_ask_slash_starts_targeted_workflow(tmp_path) -> None:
    controller = FakeWorkflowController()
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents["codex"].enabled = True
    app = TrinityTextualApp(config, controller)
    target = tmp_path.parent / "ask-target-app"
    target.mkdir()
    app.workspace_candidate = target

    async with app.run_test(size=(120, 34)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)
        screen.set_workspace_candidate(target)

        composer = screen.query_one(PromptComposer)
        composer.set_text("/ask codex --model gpt-5 설계 검토")
        composer.action_submit()
        await pilot.pause()

        assert controller.started_prompts == ["설계 검토"]
        assert controller.started_targets == [("codex",)]
        assert controller.started_models[-1] == {"codex": "gpt-5"}
        assert controller.target_workspace == target
        assert load_project_intake(app.config.effective_state_dir) is None
        assert app.current_route == "nexus"
        assert isinstance(app.screen, NexusScreen)


@pytest.mark.asyncio
async def test_start_ask_slash_errors_use_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 34)):
        app._handle_textual_slash_command("/ask")

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/ask"
        assert result.title == "질문"
        assert result.body == (
            "사용법: /ask <all|agent[,agent...]> [--model MODEL] <prompt>"
        )
        assert result.action_hint == (
            "/ask <all|agent[,agent...]> [--model MODEL] <prompt>"
        )
        assert result.severity == "warning"
        assert result.empty is True

        app._handle_textual_slash_command("/ask missing 안녕")

        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/ask"
        assert result.title == "질문"
        assert result.body == "알 수 없거나 비활성화된 에이전트: missing"
        assert result.severity == "warning"

        app._handle_textual_slash_command("/ask all --model")

        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/ask"
        assert result.title == "질문"
        assert result.body == "--model 뒤에 모델을 입력하세요."
        assert result.severity == "warning"

        app._handle_textual_slash_command("/ask all")

        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/ask"
        assert result.title == "질문"
        assert result.body == "프롬프트를 입력하세요."
        assert result.severity == "warning"
        assert controller.started_prompts == []


@pytest.mark.asyncio
async def test_start_ask_slash_no_active_agents_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController()
    config = TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    for spec in config.agents.values():
        spec.enabled = False
    app = TrinityTextualApp(config, controller)

    async with app.run_test(size=(120, 34)):
        app._handle_textual_slash_command("/ask all 안녕")

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/ask"
        assert result.title == "질문"
        assert result.body == "/ask에 사용할 활성 에이전트가 없습니다."
        assert result.action_hint == (
            "/ask <all|agent[,agent...]> [--model MODEL] <prompt>"
        )
        assert result.severity == "warning"
        assert result.empty is True
        assert controller.started_prompts == []


@pytest.mark.asyncio
async def test_start_submission_persists_selected_workspace_target(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path),
        controller,
    )
    target = tmp_path.parent / "target-app"
    target.mkdir()
    app.workspace_candidate = target

    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)
        screen.set_workspace_candidate(target)

        composer = screen.query_one(PromptComposer)
        composer.set_text("앱을 만들어줘")
        composer.action_submit()
        await pilot.pause()

        assert controller.started_prompts == ["앱을 만들어줘"]
        assert controller.target_workspace == target
        assert controller.target_control_confirmed is False
        assert app.current_route == "nexus"


@pytest.mark.asyncio
async def test_start_composer_enter_key_submits_prompt(tmp_path) -> None:
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path),
        FakeWorkflowController(),
        launch_cwd=tmp_path,
    )

    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)

        composer = screen.query_one(PromptComposer)
        composer.set_text("enter should submit")
        composer.focus_text_area()
        await pilot.press("enter")
        await pilot.pause()

        assert app.current_route == "nexus"
        assert isinstance(app.screen, NexusScreen)
        assert app.screen.initial_prompt == "enter should submit"


@pytest.mark.asyncio
async def test_start_slash_status_does_not_start_workflow(tmp_path) -> None:
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            providers=[
                ProviderSnapshot(
                    name="claude",
                    provider="claude-code",
                    enabled=True,
                    status="Queued",
                    readiness="unknown",
                )
            ]
        )
    )
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)

        composer = screen.query_one(PromptComposer)
        composer.set_text("/status ")
        composer.action_submit()
        await pilot.pause()

        assert app.current_route == "start"
        assert isinstance(app.screen, StatusCommandModal)
        assert controller.started_prompts == []
        assert controller.follow_ups == []
        assert composer.text == ""
        assert app.active_snapshot is not None
        assert app.active_snapshot.local_commands[-1].command == "/status"
        assert app.active_snapshot.local_commands[-1].title == "Status"
        assert app.active_snapshot.local_commands[-1].table_columns == ("Item", "Value")
        assert ("State", "idle") in app.active_snapshot.local_commands[-1].table_rows
        assert any(
            value.endswith("readiness=not checked")
            for _, value in app.active_snapshot.local_commands[-1].table_rows
        )
        table = app.screen.query_one("#status-command-table", Static)
        table_text = str(table.render())
        assert "Item" in table_text
        assert "Workflow" in table_text
        assert "Provider policy" in table_text
        assert "single executor" in table_text
        assert "readiness=not checked" in table_text


@pytest.mark.asyncio
async def test_start_slash_status_reports_provider_cli_setup(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents["claude"].cli_command = sys.executable
    config.agents["codex"].enabled = True
    config.agents["codex"].cli_command = "trinity-missing-cli-for-test"
    app = TrinityTextualApp(config, FakeWorkflowController())

    async with app.run_test(size=(100, 30)) as pilot:
        composer = app.screen.query_one(PromptComposer)
        composer.set_text("/status ")
        composer.action_submit()
        await pilot.pause()

        table_text = str(app.screen.query_one("#status-command-table", Static).render())
        assert "Provider CLI setup" in table_text
        assert "codex(trinity-missing-cli-for-test)" in table_text


@pytest.mark.asyncio
async def test_status_modal_contains_controls_in_narrow_korean_viewport(
    tmp_path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    config.agents["claude"].cli_command = sys.executable
    config.agents["codex"].enabled = True
    config.agents["codex"].cli_command = "trinity-missing-cli-for-test"
    config.agents["antigravity"].enabled = True
    config.agents["antigravity"].cli_command = "agy-missing-cli-for-test"
    app = TrinityTextualApp(config, FakeWorkflowController())

    async with app.run_test(size=(80, 24)) as pilot:
        composer = app.screen.query_one(PromptComposer)
        composer.set_text("/status ")
        composer.action_submit()
        await pilot.pause()

        assert isinstance(app.screen, StatusCommandModal)
        modal_shell = app.screen.query_one("#status-command-modal")
        widgets = (
            app.screen.query_one("#status-command-title", Static),
            app.screen.query_one("#status-command-body", Static),
            app.screen.query_one("#status-command-table", Static),
            app.screen.query_one("#close-status-command", Button),
        )
        for widget in widgets:
            assert widget.region.y >= modal_shell.region.y
            assert (
                widget.region.y + widget.region.height
                <= modal_shell.region.y + modal_shell.region.height
            )


@pytest.mark.asyncio
async def test_start_slash_status_uses_korean_modal_chrome(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)

        composer = screen.query_one(PromptComposer)
        composer.set_text("/status ")
        composer.action_submit()
        await pilot.pause()

        assert isinstance(app.screen, StatusCommandModal)
        assert str(app.screen.query_one("#status-command-title", Static).content) == "상태"
        assert "현재 로컬 상태" in str(
            app.screen.query_one("#status-command-body", Static).content
        )
        assert str(app.screen.query_one("#close-status-command", Button).label) == "닫기"
        assert app.active_snapshot is not None
        assert app.active_snapshot.local_commands[-1].title == "상태"
        assert app.active_snapshot.local_commands[-1].table_columns == ("항목", "값")
        assert ("상태", "대기") in app.active_snapshot.local_commands[-1].table_rows
        table_text = str(app.screen.query_one("#status-command-table", Static).render())
        assert "워크플로우" in table_text
        assert "프로바이더 정책" in table_text
        assert "단일 실행" in table_text


@pytest.mark.asyncio
async def test_start_unknown_slash_does_not_start_workflow(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path),
        controller,
        launch_cwd=tmp_path,
    )

    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)

        composer = screen.query_one(PromptComposer)
        composer.set_text("/not-a-command")
        composer.action_submit()
        await pilot.pause()

        assert app.current_route == "start"
        assert controller.started_prompts == []
        assert controller.follow_ups == []
        assert composer.text == ""
        assert app.active_snapshot is not None
        assert app.active_snapshot.local_commands[-1].command == "/not-a-command"
        assert app.active_snapshot.local_commands[-1].title == "Unknown Command"


@pytest.mark.asyncio
async def test_start_slash_context_without_session_only_notifies(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)

        composer = screen.query_one(PromptComposer)
        composer.set_text("/context ")
        composer.action_submit()
        await pilot.pause()

        assert app.current_route == "start"
        assert isinstance(app.screen, StartScreen)
        assert controller.started_prompts == []
        assert controller.follow_ups == []
        assert composer.text == ""
        assert app.active_snapshot is None


@pytest.mark.asyncio
async def test_start_slash_context_with_current_snapshot_shows_modal(tmp_path) -> None:
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            session_id="wf-current",
            goal="Current session goal",
            state="blueprint_ready",
            synthesis=SynthesisSnapshot(
                summary="Current session summary.",
                consensus_progress="blueprint ready",
            ),
        )
    )
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)

        composer = screen.query_one(PromptComposer)
        composer.set_text("/context ")
        composer.action_submit()
        await pilot.pause()

        assert app.current_route == "start"
        assert isinstance(app.screen, ContextCommandModal)
        assert controller.started_prompts == []
        assert controller.follow_ups == []
        assert app.active_snapshot is not None
        assert app.active_snapshot.local_commands[-1].command == "/context"
        assert "Current session goal" in app.active_snapshot.local_commands[-1].body
        body = app.screen.query_one("#context-command-body", Markdown)
        assert body is not None


@pytest.mark.asyncio
async def test_start_slash_context_uses_korean_modal_and_body(tmp_path) -> None:
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            session_id="wf-current",
            goal="현재 세션 목표",
            state="blueprint_ready",
            synthesis=SynthesisSnapshot(
                summary="현재 세션 요약.",
                consensus_progress="blueprint ready",
            ),
        )
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)

        composer = screen.query_one(PromptComposer)
        composer.set_text("/context ")
        composer.action_submit()
        await pilot.pause()

        assert isinstance(app.screen, ContextCommandModal)
        assert str(app.screen.query_one("#context-command-title", Static).content) == (
            "현재 세션 컨텍스트"
        )
        assert str(app.screen.query_one("#close-context-command", Button).label) == "닫기"
        assert app.active_snapshot is not None
        body = app.active_snapshot.local_commands[-1].body
        assert "- 워크플로우: `wf-current`" in body
        assert "### 종합" in body


@pytest.mark.asyncio
async def test_context_modal_keeps_controls_in_narrow_viewport(tmp_path) -> None:
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            session_id="wf-context",
            goal="긴 컨텍스트 확인",
            state="executing",
            round_num=3,
            synthesis=SynthesisSnapshot(
                summary="요약 " * 80,
                consensus_progress="ready",
            ),
            decisions=[
                f"결정 {index}: 긴 결정 내용입니다."
                for index in range(15)
            ],
            work_packages=[
                f"WP-{index:03d} 긴 작업 패키지 설명입니다."
                for index in range(15)
            ],
            workflow_events=[
                f"이벤트 {index}: 진행 로그입니다."
                for index in range(20)
            ],
        )
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(80, 24)) as pilot:
        app._handle_textual_slash_command("/context")
        await pilot.pause()

        assert isinstance(app.screen, ContextCommandModal)
        modal_shell = app.screen.query_one("#context-command-modal")
        widgets = (
            app.screen.query_one("#context-command-title", Static),
            app.screen.query_one("#context-command-content"),
            app.screen.query_one("#close-context-command", Button),
        )
        for widget in widgets:
            assert widget.region.y >= modal_shell.region.y
            assert (
                widget.region.y + widget.region.height
                <= modal_shell.region.y + modal_shell.region.height
            )


@pytest.mark.asyncio
async def test_nexus_slash_workflow_does_not_submit_followup(tmp_path) -> None:
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(session_id="wf-fake", goal="game", state="blueprint_ready")
    )
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)

        composer = screen.query_one("#nexus-composer", PromptComposer)
        composer.set_text("/workflow ")
        composer.action_submit()
        await pilot.pause()

        assert app.current_route == "nexus"
        assert controller.follow_ups == []
        assert screen.follow_ups == []
        assert composer.text == ""
        central = screen.query_one(CentralAgentView)
        assert central.snapshot is not None
        assert central.snapshot.local_commands[-1].command == "/workflow"
        assert central.snapshot.local_commands[-1].title == "Workflow"
        assert "Command Result" in central.render_markdown()
        assert "**/workflow - Workflow**" in central.render_markdown()


@pytest.mark.asyncio
async def test_nexus_execute_retry_slash_opens_retry_modal(tmp_path) -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-retry",
        goal="game",
        state="failed",
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Client",
                owner_agent="codex",
                status="failed",
                topic="Client",
                retryable=True,
            ),
            WorkPackageSnapshot(
                id="WP-002",
                title="Docs",
                owner_agent="claude",
                status="done",
                topic="Docs",
                retryable=False,
                retry_disabled_reason="already done",
            ),
        ],
    )
    controller = FakeWorkflowController(snapshot)
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)

        composer = screen.query_one("#nexus-composer", PromptComposer)
        composer.set_text("/execute-retry custom WP-001")
        composer.action_submit()
        await pilot.pause()

        assert isinstance(app.screen, ExecutionRetryModal)
        assert controller.retry_previews == [("custom", ["WP-001"])]
        assert controller.follow_ups == []
        assert composer.text == ""


@pytest.mark.asyncio
async def test_nexus_execute_retry_empty_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController(WorkflowNexusSnapshot(session_id="wf-empty"))
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._handle_textual_slash_command("/execute-retry")
        await pilot.pause()

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/execute-retry"
        assert result.title == "실행 재시도"
        assert result.body == "현재 워크플로우에 사용할 수 있는 작업 패키지가 없습니다."
        assert result.action_hint == "하나 이상의 작업 패키지를 준비하고 실행하세요."
        assert result.severity == "warning"
        assert result.empty is True


@pytest.mark.asyncio
async def test_execute_retry_selection_opens_workspace_picker_when_required(
    tmp_path,
) -> None:
    snapshot = WorkflowNexusSnapshot(session_id="wf-retry")
    controller = FakeWorkflowController(snapshot)
    controller.retry_outcome = TextualWorkflowOutcome(
        snapshot,
        message="Choose a target workspace before retrying execution.",
        target_workspace_required=True,
    )
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)
    selection = ExecutionRetrySelection("custom", ("WP-001",))

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._on_execute_retry_selected(selection)
        await pilot.pause()

        assert controller.retry_confirms == [("custom", ["WP-001"])]
        assert app._pending_execute_retry is selection
        assert isinstance(app.screen, WorkspacePicker)


@pytest.mark.asyncio
async def test_execute_retry_selection_switches_to_execution_when_requested(
    tmp_path,
) -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-retry",
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Client",
                owner_agent="codex",
                status="failed",
                retryable=True,
            )
        ],
    )
    controller = FakeWorkflowController(snapshot)
    controller.retry_outcome = TextualWorkflowOutcome(
        snapshot,
        message="Retrying work packages: WP-001.",
        execution_requested=True,
    )
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._on_execute_retry_selected(
            ExecutionRetrySelection("custom", ("WP-001",))
        )
        await pilot.pause()

        assert controller.retry_confirms == [("custom", ["WP-001"])]
        assert app.current_route == "execution"
        assert isinstance(app.screen, ExecutionMatrixScreen)


@pytest.mark.asyncio
async def test_execution_retry_empty_notify_uses_korean_labels(
    tmp_path,
    monkeypatch,
) -> None:
    snapshot = WorkflowNexusSnapshot(session_id="wf-empty")
    controller = FakeWorkflowController(snapshot)
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )
    notifications: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        app,
        "notify",
        lambda message, **kwargs: notifications.append(
            (message, str(kwargs.get("title", "")), str(kwargs.get("severity", "info")))
        ),
    )

    async with app.run_test(size=(120, 40)) as pilot:
        event = ExecutionMatrixScreen.RetryRequested(snapshot)
        app.on_execution_matrix_screen_retry_requested(event)
        await pilot.pause()

        assert notifications == [
            (
                "현재 워크플로우에 사용할 수 있는 작업 패키지가 없습니다.",
                "실행 재시도",
                "warning",
            )
        ]


@pytest.mark.asyncio
async def test_nexus_central_execution_retry_action_opens_retry_modal(tmp_path) -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-central-retry",
        goal="game",
        state="failed",
        execution_recovery=ExecutionRecoverySnapshot(
            state="failed",
            retry_candidates=("WP-001",),
        ),
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Client",
                owner_agent="codex",
                status="failed",
                topic="Client",
                retryable=True,
            ),
        ],
    )
    controller = FakeWorkflowController(snapshot)
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(100, 30)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)
        screen.apply_snapshot(controller.snapshot())
        await pilot.pause()

        assert screen.query_one("#central-action-title", Static).content == (
            "실행 재시도 결정"
        )
        buttons = list(screen.query("#central-actions Button"))
        assert [str(button.label) for button in buttons] == ["실패 작업 재시도"]

        buttons[0].press()
        await pilot.pause()

        assert isinstance(app.screen, ExecutionRetryModal)

    assert controller.retry_previews == [("all", [])]


def test_execution_retry_modal_limits_rows_to_retry_candidates() -> None:
    modal = ExecutionRetryModal(
        WorkflowNexusSnapshot(
            work_package_details=[
                WorkPackageSnapshot(
                    id="WP-001",
                    title="Client",
                    owner_agent="codex",
                    status="failed",
                    topic="Client",
                    retryable=True,
                ),
                WorkPackageSnapshot(
                    id="WP-002",
                    title="Docs",
                    owner_agent="claude",
                    status="done",
                    topic="Docs",
                    retryable=False,
                    retry_disabled_reason="already done",
                ),
                WorkPackageSnapshot(
                    id="WP-003",
                    title="Backend",
                    owner_agent="antigravity",
                    status="blocked",
                    topic="Backend",
                    retryable=True,
                ),
            ],
        )
    )

    assert [package.id for package in modal.display_packages()] == ["WP-001", "WP-003"]
    assert modal.ids_for_selector("all") == ("WP-001", "WP-003")
    modal.selector = "failed"
    assert [package.id for package in modal.display_packages()] == ["WP-001"]


def test_execution_retry_modal_large_snapshot_keeps_only_retry_candidates() -> None:
    details = [
        WorkPackageSnapshot(
            id=f"WP-{index:03d}",
            title=f"Package {index}",
            owner_agent="codex",
            status="done",
            retryable=False,
            retry_disabled_reason="already done",
        )
        for index in range(1, 101)
    ]
    details[9] = WorkPackageSnapshot(
        id="WP-010",
        title="Failed package",
        owner_agent="codex",
        status="failed",
        retryable=True,
    )
    details[49] = WorkPackageSnapshot(
        id="WP-050",
        title="Blocked package",
        owner_agent="claude",
        status="blocked",
        retryable=True,
    )
    details[74] = WorkPackageSnapshot(
        id="WP-075",
        title="Running package",
        owner_agent="antigravity",
        status="running",
        retryable=True,
    )
    modal = ExecutionRetryModal(
        WorkflowNexusSnapshot(work_package_details=details),
    )

    assert [package.id for package in modal.display_packages()] == [
        "WP-010",
        "WP-050",
        "WP-075",
    ]
    assert modal.ids_for_selector("all") == ("WP-010", "WP-050", "WP-075")
    modal.selector = "blocked"
    assert [package.id for package in modal.display_packages()] == ["WP-050"]


def test_execution_retry_modal_custom_keeps_selected_retry_candidates() -> None:
    snapshot = WorkflowNexusSnapshot(
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Client",
                owner_agent="codex",
                status="failed",
                retryable=True,
            ),
            WorkPackageSnapshot(
                id="WP-002",
                title="Docs",
                owner_agent="claude",
                status="done",
                retryable=False,
                retry_disabled_reason="already done",
            ),
            WorkPackageSnapshot(
                id="WP-003",
                title="Backend",
                owner_agent="antigravity",
                status="blocked",
                retryable=True,
            ),
        ],
    )

    modal = ExecutionRetryModal(
        snapshot,
        selector="custom",
        package_ids=("WP-002", "WP-003"),
    )

    assert [package.id for package in modal.display_packages()] == ["WP-001", "WP-003"]
    assert modal.selected_package_ids() == ("WP-003",)


def test_execution_retry_modal_supports_korean_chrome_labels() -> None:
    modal = ExecutionRetryModal(
        WorkflowNexusSnapshot(
            target_workspace="/workspace/game",
            execution_recovery=ExecutionRecoverySnapshot(
                state="failed",
                target_workspace="/workspace/game",
            ),
            work_package_details=[
                WorkPackageSnapshot(
                    id="WP-001",
                    title="Client",
                    owner_agent="codex",
                    status="failed",
                    retryable=True,
                ),
            ],
        ),
        lang="ko",
    )

    assert modal.label_text("title") == "실행 재시도"
    assert modal.filter_label("failed") == "실패"
    assert modal.summary_text() == "복구: 실패  대상: /workspace/game"
    assert modal.header_text().startswith("작업 ID 상태")
    assert modal.selected_text() == "선택됨: WP-001"


@pytest.mark.asyncio
async def test_execution_retry_modal_localizes_korean_status_cells(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path, lang="ko"))
    modal = ExecutionRetryModal(
        WorkflowNexusSnapshot(
            work_package_details=[
                WorkPackageSnapshot(
                    id="WP-001",
                    title="Client",
                    owner_agent="codex",
                    status="failed",
                    retryable=True,
                ),
                WorkPackageSnapshot(
                    id="WP-002",
                    title="Backend",
                    owner_agent="claude",
                    status="blocked",
                    retryable=True,
                    current_executor="codex",
                    repair_attempt_count=2,
                    repair_max_attempts=3,
                    repair_blocked_reason="duplicate_required_changes",
                ),
                WorkPackageSnapshot(
                    id="WP-003",
                    title="Runtime",
                    owner_agent="antigravity",
                    status="running",
                    retryable=True,
                ),
            ],
        ),
        lang="ko",
    )

    async with app.run_test(size=(120, 36)) as pilot:
        app.push_screen(modal)
        await pilot.pause()

        statuses = [
            str(status.render())
            for status in app.screen.query(".retry-row .retry-status")
        ]
        executors = [
            str(executor.render())
            for executor in app.screen.query(".retry-row .retry-executor")
        ]
        notes = [
            str(note.render())
            for note in app.screen.query(".retry-row .retry-note")
        ]

    assert statuses == ["실패", "차단", "실행 중"]
    assert executors == ["-", "codex 대체", "-"]
    assert notes[1] == "복구 2/3: duplicate_required_changes"


def test_execution_retry_modal_keeps_english_chrome_labels() -> None:
    modal = ExecutionRetryModal(
        WorkflowNexusSnapshot(
            work_package_details=[
                WorkPackageSnapshot(
                    id="WP-001",
                    title="Client",
                    owner_agent="codex",
                    status="failed",
                    retryable=True,
                ),
            ],
        )
    )

    assert modal.label_text("title") == "Execute Retry"
    assert modal.filter_label("failed") == "Failed"
    assert modal.summary_text() == "Recovery: none  Target: (not selected)"
    assert modal.header_text().startswith("WP      Status")
    assert modal.selected_text() == "Selected: WP-001"


@pytest.mark.asyncio
async def test_execution_retry_modal_keeps_english_status_cells(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))
    modal = ExecutionRetryModal(
        WorkflowNexusSnapshot(
            work_package_details=[
                WorkPackageSnapshot(
                    id="WP-001",
                    title="Client",
                    owner_agent="codex",
                    status="failed",
                    retryable=True,
                ),
            ],
        )
    )

    async with app.run_test(size=(120, 36)) as pilot:
        app.push_screen(modal)
        await pilot.pause()

        statuses = [
            str(status.render())
            for status in app.screen.query(".retry-row .retry-status")
        ]

    assert statuses == ["failed"]


@pytest.mark.asyncio
async def test_start_slash_workflow_uses_generic_local_command_modal(
    tmp_path,
) -> None:
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(session_id="wf-fake", goal="game", state="blueprint_ready")
    )
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)

        composer = screen.query_one(PromptComposer)
        composer.set_text("/workflow ")
        composer.action_submit()
        await pilot.pause()

        assert app.current_route == "start"
        assert isinstance(app.screen, LocalCommandModal)
        assert controller.started_prompts == []
        assert controller.follow_ups == []
        assert composer.text == ""
        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/workflow"
        assert result.title == "Workflow"
        assert result.table_columns == ("Item", "Value")
        body = app.screen.query_one("#local-command-body", Markdown)
        assert body is not None
        assert "Goal: game" in result.body
        table = app.screen.query_one("#local-command-table", Static)
        assert "Workflow" not in str(table.render())
        assert "State" in str(table.render())


@pytest.mark.asyncio
async def test_start_slash_workflow_uses_korean_local_command_modal_chrome(
    tmp_path,
) -> None:
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(session_id="wf-fake", goal="game", state="blueprint_ready")
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)

        composer = screen.query_one(PromptComposer)
        composer.set_text("/workflow ")
        composer.action_submit()
        await pilot.pause()

        assert isinstance(app.screen, LocalCommandModal)
        assert str(app.screen.query_one("#close-local-command", Button).label) == "닫기"
        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.title == "워크플로우"
        assert result.table_columns == ("항목", "값")
        assert ("상태", "설계 준비") in result.table_rows
        assert "- 상태: `설계 준비`" in result.body
        assert "- 목표: game" in result.body
        table = app.screen.query_one("#local-command-table", Static)
        assert "상태" in str(table.render())


@pytest.mark.asyncio
async def test_start_slash_questions_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            session_id="wf-fake",
            goal="game",
            state="needs_user_decision",
            questions=[
                QuestionSnapshot(
                    id="q-1",
                    question="Theme?",
                    options=["dark", "light"],
                    recommended_option="dark",
                )
            ],
        )
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)

        composer = screen.query_one(PromptComposer)
        composer.set_text("/questions ")
        composer.action_submit()
        await pilot.pause()

        assert isinstance(app.screen, LocalCommandModal)
        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/questions"
        assert result.title == "질문"
        assert result.table_columns == ("ID", "상태", "질문", "선택지")
        assert result.table_rows[0] == ("q-1", "열림", "Theme?", "dark, light")
        assert result.action_hint.startswith("질문 패널")
        assert "추천: dark" in result.body
        assert "질문 패널 버튼을 사용하거나" in result.body
        table = app.screen.query_one("#local-command-table", Static)
        assert "선택지" in str(table.render())


@pytest.mark.asyncio
async def test_start_slash_decisions_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            session_id="wf-fake",
            goal="game",
            decisions=["Use dark theme."],
        )
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)

        composer = screen.query_one(PromptComposer)
        composer.set_text("/decisions ")
        composer.action_submit()
        await pilot.pause()

        assert isinstance(app.screen, LocalCommandModal)
        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/decisions"
        assert result.title == "결정"
        assert result.table_columns == ("#", "결정")
        assert result.table_rows == (("1", "Use dark theme."),)
        assert result.action_hint == ""
        assert "1. Use dark theme." in result.body
        table = app.screen.query_one("#local-command-table", Static)
        assert "결정" in str(table.render())


@pytest.mark.asyncio
async def test_start_slash_empty_decisions_uses_korean_hint(tmp_path) -> None:
    controller = FakeWorkflowController(WorkflowNexusSnapshot(session_id="wf-fake"))
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(100, 30)):
        app._handle_textual_slash_command("/decisions")

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.empty is True
        assert result.body == "현재 세션에 기록된 워크플로우 결정이 없습니다."
        assert result.action_hint.startswith("대기 중인 질문")


@pytest.mark.asyncio
async def test_start_slash_packages_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            session_id="wf-fake",
            central_work_packages=["WP-001 claude: Plan"],
            work_packages=["WP-002 codex: Build"],
        )
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)

        composer = screen.query_one(PromptComposer)
        composer.set_text("/packages ")
        composer.action_submit()
        await pilot.pause()

        assert isinstance(app.screen, LocalCommandModal)
        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/packages"
        assert result.title == "작업 패키지"
        assert result.table_columns == ("#", "출처", "작업 패키지")
        assert result.table_rows[0] == ("1", "중앙", "WP-001 claude: Plan")
        assert result.table_rows[1] == ("2", "로컬", "WP-002 codex: Build")
        assert "1. **중앙** WP-001 claude: Plan" in result.body
        table = app.screen.query_one("#local-command-table", Static)
        assert "작업 패키지" in str(table.render())


@pytest.mark.asyncio
async def test_start_slash_empty_packages_uses_korean_hint(tmp_path) -> None:
    controller = FakeWorkflowController(WorkflowNexusSnapshot(session_id="wf-fake"))
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(100, 30)):
        app._handle_textual_slash_command("/packages")

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.empty is True
        assert result.body == "현재 세션에 생성된 워크플로우 작업 패키지가 없습니다."
        assert result.action_hint.startswith("설계안")


@pytest.mark.asyncio
async def test_start_slash_subtasks_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            session_id="wf-fake",
            subtasks=[
                SubtaskSnapshot(
                    id="ST-001",
                    parent_package_id="WP-001",
                    parent_agent="claude",
                    delegated_to="codex",
                    objective="Implement",
                    result_summary="Done",
                    status="done",
                )
            ],
        )
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)

        composer = screen.query_one(PromptComposer)
        composer.set_text("/subtasks ")
        composer.action_submit()
        await pilot.pause()

        assert isinstance(app.screen, LocalCommandModal)
        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/subtasks"
        assert result.title == "하위 작업"
        assert result.table_columns == ("ID", "작업 패키지", "위임 대상", "상태", "요약")
        assert result.table_rows[0] == ("ST-001", "WP-001", "codex", "완료", "Done")
        assert "1. **ST-001** [완료] WP-001 -> codex: Done" in result.body
        table = app.screen.query_one("#local-command-table", Static)
        assert "위임 대상" in str(table.render())


@pytest.mark.asyncio
async def test_start_slash_empty_subtasks_uses_korean_hint(tmp_path) -> None:
    controller = FakeWorkflowController(WorkflowNexusSnapshot(session_id="wf-fake"))
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(100, 30)):
        app._handle_textual_slash_command("/subtasks")

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.empty is True
        assert result.body == "현재 세션에 기록된 프로바이더 위임 하위 작업이 없습니다."
        assert result.action_hint.startswith("실행 중인")


@pytest.mark.asyncio
async def test_nexus_unknown_slash_does_not_submit_followup(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)

        composer = screen.query_one("#nexus-composer", PromptComposer)
        composer.set_text("/not-a-command")
        composer.action_submit()
        await pilot.pause()

        assert app.current_route == "nexus"
        assert controller.follow_ups == []
        assert screen.follow_ups == []
        assert composer.text == ""
        central = screen.query_one(CentralAgentView)
        assert central.snapshot is not None
        assert central.snapshot.local_commands[-1].command == "/not-a-command"
        assert central.snapshot.local_commands[-1].title == "Unknown Command"
        assert "Command Result" in central.render_markdown()
        assert "**/not-a-command - Unknown Command**" in central.render_markdown()


@pytest.mark.asyncio
async def test_nexus_save_and_target_commands_record_local_results(
    tmp_path,
) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)

        composer = screen.query_one("#nexus-composer", PromptComposer)
        composer.set_text("/save ")
        composer.action_submit()
        await pilot.pause()

        assert controller.follow_ups == []
        central = screen.query_one(CentralAgentView)
        assert central.snapshot is not None
        save_result = central.snapshot.local_commands[-1]
        assert save_result.command == "/save"
        assert save_result.title == "Save"
        assert "persisted automatically" in save_result.body

        composer.set_text("/target ")
        composer.action_submit()
        await pilot.pause()

        target_result = central.snapshot.local_commands[-1]
        assert target_result.command == "/target"
        assert target_result.title == "Target"
        assert "Current target" in target_result.body
        assert "Use `/target <path>`" in central.render_markdown()
        assert controller.started_prompts == []
        assert controller.follow_ups == []


@pytest.mark.asyncio
async def test_nexus_save_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)):
        app._handle_textual_slash_command("/save")

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/save"
        assert result.title == "저장"
        assert result.body == (
            "Trinity 워크플로우는 자동으로 저장됩니다. "
            "마크다운 리포트 내보내기는 /report save를 사용하세요."
        )
        assert controller.started_prompts == []
        assert controller.follow_ups == []


@pytest.mark.asyncio
async def test_nexus_target_current_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)):
        app._handle_textual_slash_command("/target")

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/target"
        assert result.title == "대상"
        assert result.body == "현재 대상: `(미설정)`"
        assert result.action_hint == "실행 전에 `/target <path>`를 사용하세요."
        assert result.empty is True


@pytest.mark.asyncio
async def test_nexus_target_path_outside_control_repo_uses_korean_labels(
    tmp_path,
) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        outside_target = tmp_path.parent / f"{tmp_path.name}-ko-target"
        app._handle_textual_slash_command(f"/target {outside_target}")
        await pilot.pause()

        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/target"
        assert result.title == "대상"
        assert result.body.startswith("대상 작업 폴더:")
        assert result.table_columns == ("항목", "값")
        assert ("경로", str(outside_target.resolve())) in result.table_rows
        assert ("제어 저장소 내부", "아니오") in result.table_rows
        assert ("제어 저장소 확인", "아니오") in result.table_rows


@pytest.mark.asyncio
async def test_nexus_target_cancel_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        inside_target = tmp_path / "inside-control-repo"
        app._handle_textual_slash_command(f"/target {inside_target}")
        await pilot.pause()
        assert isinstance(app.screen, TargetWorkspaceConfirmModal)
        assert str(app.screen.query_one("#target-confirm-title", Static).content) == (
            "제어 저장소 대상 확인"
        )
        assert "Trinity 제어 저장소 안" in str(
            app.screen.query_one("#target-confirm-body", Static).content
        )
        paths = str(app.screen.query_one("#target-confirm-paths", Static).content)
        assert "대상:" in paths
        assert "제어 저장소:" in paths
        assert str(app.screen.query_one("#cancel-target-confirm", Button).label) == "취소"
        assert str(app.screen.query_one("#confirm-target", Button).label) == "그래도 사용"

        app.screen.query_one("#cancel-target-confirm", Button).press()
        await pilot.pause()

        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/target"
        assert result.title == "대상"
        assert result.body == "대상 작업 폴더 선택을 취소했습니다."
        assert result.action_hint == (
            "Trinity 제어 저장소 밖의 작업 폴더를 선택하세요."
        )


@pytest.mark.asyncio
async def test_nexus_target_path_inside_control_repo_requires_confirmation(
    tmp_path,
) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        inside_target = tmp_path / "inside-control-repo"
        app._handle_textual_slash_command(f"/target {inside_target}")
        await pilot.pause()

        assert isinstance(app.screen, TargetWorkspaceConfirmModal)
        assert controller.target_workspace is None

        app.screen.query_one("#cancel-target-confirm", Button).press()
        await pilot.pause()
        assert controller.target_workspace is None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/target"
        assert "cancelled" in result.body

        app._handle_textual_slash_command(f"/target {inside_target}")
        await pilot.pause()
        assert isinstance(app.screen, TargetWorkspaceConfirmModal)
        app.screen.query_one("#confirm-target", Button).press()
        await pilot.pause()

        assert controller.target_workspace == inside_target.resolve()
        assert controller.target_control_confirmed is True
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/target"
        assert ("Control repo confirmed", "yes") in result.table_rows


@pytest.mark.asyncio
async def test_nexus_target_path_outside_control_repo_sets_without_confirmation(
    tmp_path,
) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        outside_target = tmp_path.parent / f"{tmp_path.name}-target"
        app._handle_textual_slash_command(f"/target {outside_target}")
        await pilot.pause()

        assert app.current_route == "nexus"
        assert not isinstance(app.screen, TargetWorkspaceConfirmModal)
        assert controller.target_workspace == outside_target.resolve()
        assert controller.target_control_confirmed is False
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/target"
        assert ("Inside control repo", "no") in result.table_rows


@pytest.mark.asyncio
async def test_workspace_preflight_inside_control_repo_requires_confirmation(
    tmp_path,
) -> None:
    controller = FakeWorkflowController(WorkflowNexusSnapshot(state="blueprint_ready"))
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)
    preflight = build_preflight(tmp_path, WorkflowNexusSnapshot(state="blueprint_ready"))

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._on_workspace_preflight(preflight)
        await pilot.pause()

        assert isinstance(app.screen, TargetWorkspaceConfirmModal)
        assert controller.target_workspace is None

        app.screen.query_one("#confirm-target", Button).press()
        await pilot.pause()

        assert controller.target_workspace == tmp_path
        assert controller.target_control_confirmed is True


def test_workspace_preflight_localizes_branch_placeholder(tmp_path) -> None:
    preflight = build_preflight(tmp_path, WorkflowNexusSnapshot())

    assert preflight.branch == "(none)"
    assert "Branch: (none)" in preflight.render(lang="en")
    assert "브랜치: (없음)" in preflight.render(lang="ko")


@pytest.mark.asyncio
async def test_start_slash_help_uses_registry_backed_local_modal(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)

        composer = screen.query_one(PromptComposer)
        composer.set_text("/help ")
        composer.action_submit()
        await pilot.pause()

        assert app.current_route == "start"
        assert isinstance(app.screen, LocalCommandModal)
        assert controller.started_prompts == []
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/help"
        assert result.title == "Trinity Commands"
        assert result.table_columns == (
            "Command",
            "Category",
            "Agent Call",
            "Summary",
        )
        assert any(row[0] == "/status" for row in result.table_rows)
        assert "handled before provider prompts" in result.body


@pytest.mark.asyncio
async def test_start_slash_help_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)) as pilot:
        app._handle_textual_slash_command("/help")
        await pilot.pause()

        assert isinstance(app.screen, LocalCommandModal)
        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/help"
        assert result.title == "Trinity 명령"
        assert result.table_columns == ("명령", "카테고리", "에이전트 호출", "요약")
        assert any(row[0] == "/status" for row in result.table_rows)
        assert "Trinity 소유 슬래시 명령" in result.body
        assert "### 카테고리" in result.body


@pytest.mark.asyncio
async def test_local_command_modal_keeps_help_controls_in_narrow_viewport(
    tmp_path,
) -> None:
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        FakeWorkflowController(),
    )

    async with app.run_test(size=(80, 24)) as pilot:
        app._handle_textual_slash_command("/help")
        await pilot.pause()

        assert isinstance(app.screen, LocalCommandModal)
        modal_shell = app.screen.query_one("#local-command-modal")
        widgets = (
            app.screen.query_one("#local-command-title", Static),
            app.screen.query_one("#local-command-content"),
            app.screen.query_one("#close-local-command", Button),
        )
        for widget in widgets:
            assert widget.region.y >= modal_shell.region.y
            assert (
                widget.region.y + widget.region.height
                <= modal_shell.region.y + modal_shell.region.height
            )


@pytest.mark.asyncio
async def test_nexus_lookup_commands_record_tables_from_current_snapshot(
    tmp_path,
) -> None:
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            session_id="wf-current",
            goal="Build game",
            state="reviewing",
            questions=[
                QuestionSnapshot(
                    id="q-1",
                    question="Choose style?",
                    options=["pixel", "flat"],
                    status="open",
                )
            ],
            decisions=["Use pixel art."],
            central_work_packages=["WP-001 claude: Plan systems (deps=-; files=-)"],
            work_packages=["WP-001 claude: Plan systems (done)"],
            subtasks=[
                SubtaskSnapshot(
                    id="ST-001",
                    parent_package_id="WP-001",
                    parent_agent="claude",
                    delegated_to="code-search",
                    objective="Find patterns.",
                    result_summary="Found registry.",
                    status="done",
                )
            ],
        )
    )
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        for command in ("/questions", "/decisions", "/packages", "/subtasks"):
            app._handle_textual_slash_command(command)
            await pilot.pause()
            result = app.active_snapshot.local_commands[-1]
            assert result.command == command
            assert result.table_columns
            assert result.table_rows
            assert result.empty is False

        assert controller.started_prompts == []
        assert controller.follow_ups == []
        assert app.active_snapshot.local_commands[-1].table_rows[0][0] == "ST-001"


@pytest.mark.asyncio
async def test_nexus_empty_lookup_commands_record_empty_states(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._handle_textual_slash_command("/history")
        await pilot.pause()
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/history"
        assert result.empty is True
        assert "No local history" in result.body

        for command in ("/questions", "/decisions", "/packages", "/subtasks"):
            app._handle_textual_slash_command(command)
            await pilot.pause()
            result = app.active_snapshot.local_commands[-1]
            assert result.command == command
            assert result.empty is True
            assert result.table_rows == ()

        assert controller.started_prompts == []
        assert controller.follow_ups == []


@pytest.mark.asyncio
async def test_start_slash_history_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            session_id="wf-fake",
            goal="game",
            state="reviewing",
            execution_log=["WP-001 codex: done"],
        )
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)

        composer = screen.query_one(PromptComposer)
        composer.set_text("/history ")
        composer.action_submit()
        await pilot.pause()

        assert isinstance(app.screen, LocalCommandModal)
        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/history"
        assert result.title == "워크플로우 이력"
        assert result.table_columns == ("종류", "항목")
        assert ("워크플로우", "wf-fake") in result.table_rows
        assert ("실행", "WP-001 codex: done") in result.table_rows
        assert "### 최근 실행 로그" in result.body
        assert "### 최근 로컬 항목" in result.body
        table = app.screen.query_one("#local-command-table", Static)
        assert "워크플로우" in str(table.render())


@pytest.mark.asyncio
async def test_start_slash_empty_history_uses_korean_hint(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(100, 30)):
        app._handle_textual_slash_command("/history")

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.empty is True
        assert result.body == "현재 세션에 기록된 로컬 이력이 없습니다."
        assert result.action_hint.startswith("프롬프트 실행")
        assert result.table_columns == ("종류", "항목")


@pytest.mark.asyncio
async def test_start_slash_review_uses_korean_labels(tmp_path) -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-review",
        state="reviewing",
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Plan",
                owner_agent="claude",
                status="done",
            )
        ],
    )
    controller = FakeWorkflowController(snapshot)
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(100, 30)):
        app._handle_textual_slash_command("/review wp")

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/review"
        assert result.title == "리뷰"
        assert result.body == "리뷰를 시작했습니다: wp."
        assert result.table_columns == ("항목", "값")
        assert ("워크플로우", "wf-review") in result.table_rows
        assert ("대기 중 작업 패키지 리뷰", "WP-001") in result.table_rows
        assert result.action_hint.startswith("`/review wp`")
        assert controller.review_requests == [("wp",)]


@pytest.mark.asyncio
async def test_start_slash_improve_uses_korean_labels(tmp_path) -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-improve",
        state="post_review_ready",
        supplemental_round=1,
        post_review_items=[
            PostReviewActionSnapshot(
                id="AI-001",
                title="Fix tests",
                summary="Fix tests",
                severity="high",
                status="pending",
                kind="test",
            )
        ],
    )
    controller = FakeWorkflowController(snapshot)
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(100, 30)):
        app._handle_textual_slash_command("/improve high")

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/improve"
        assert result.title == "개선"
        assert result.body == "개선을 요청했습니다: high."
        assert result.table_columns == ("항목", "값")
        assert ("워크플로우", "wf-improve") in result.table_rows
        assert ("보충 라운드", "1") in result.table_rows
        assert (
            "AI-001",
            "대기; 심각도=높음; 종류=테스트; 제목=Fix tests",
        ) in result.table_rows
        assert result.action_hint.startswith("`/improve high`")
        assert controller.improve_requests == [("high",)]


@pytest.mark.asyncio
async def test_nexus_report_without_data_records_empty_result(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._handle_textual_slash_command("/report")
        await pilot.pause()

        assert app.current_route == "nexus"
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/report"
        assert result.title == "Report"
        assert result.empty is True
        assert "No workflow data available" in result.body
        assert controller.started_prompts == []
        assert controller.follow_ups == []


@pytest.mark.asyncio
async def test_nexus_report_without_data_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._handle_textual_slash_command("/report")
        await pilot.pause()

        assert app.current_route == "nexus"
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/report"
        assert result.title == "리포트"
        assert result.empty is True
        assert result.body == "리포트로 표시할 워크플로우 데이터가 없습니다."
        assert result.action_hint == (
            "리포트를 열려면 먼저 워크플로우를 시작하거나 재개하세요."
        )


@pytest.mark.asyncio
async def test_nexus_report_save_records_export_path(tmp_path) -> None:
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            session_id="wf-current",
            goal="Build game",
            state="done",
            decisions=["Ship it."],
        )
    )
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._handle_textual_slash_command("/report save")
        await pilot.pause()

        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/report"
        assert result.result_kind == "path"
        assert result.table_rows
        path = Path(result.table_rows[0][1])
        assert path.exists()
        assert path.read_text(encoding="utf-8").startswith("# Deliberation Report")


@pytest.mark.asyncio
async def test_nexus_report_save_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            session_id="wf-current",
            goal="게임 만들기",
            state="done",
            decisions=["출시한다."],
        )
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._handle_textual_slash_command("/report save")
        await pilot.pause()

        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/report"
        assert result.title == "리포트"
        assert result.body.startswith("리포트 저장됨:")
        assert result.table_columns == ("항목", "값")
        assert result.table_rows[0][0] == "경로"
        path = Path(result.table_rows[0][1])
        assert path.exists()


@pytest.mark.asyncio
async def test_nexus_setting_commands_show_current_tables(tmp_path) -> None:
    controller = FakeWorkflowController()
    config = TrinityConfig.default_config(project_dir=tmp_path)
    app = TrinityTextualApp(config, controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        for command in ("/rounds", "/agent", "/caveman"):
            app._handle_textual_slash_command(command)
            await pilot.pause()
            result = app.active_snapshot.local_commands[-1]
            assert result.command == command
            assert result.table_columns
            assert result.table_rows
            assert SESSION_ONLY_SETTING_NOTICE in result.body

        assert controller.started_prompts == []
        assert controller.follow_ups == []


@pytest.mark.asyncio
async def test_nexus_rounds_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController()
    config = TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    app = TrinityTextualApp(config, controller)

    async with app.run_test(size=(120, 40)):
        app._handle_textual_slash_command("/rounds")

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/rounds"
        assert result.title == "라운드"
        assert result.body.startswith("현재 최대 라운드:")
        assert result.table_columns == ("항목", "값")
        assert ("현재 최대 라운드", str(config.max_deliberation_rounds)) in result.table_rows
        assert ("허용 범위", "1..20") in result.table_rows
        assert result.action_hint == "`/rounds <1..20>`로 이 세션의 값을 변경하세요."

        app._handle_textual_slash_command("/rounds 7")

        result = app.active_snapshot.local_commands[-1]
        assert config.max_deliberation_rounds == 7
        assert result.command == "/rounds"
        assert result.title == "라운드"
        assert result.body.startswith("이 세션의 최대 라운드를 `7`로 설정했습니다.")
        assert ("현재 최대 라운드", "7") in result.table_rows


@pytest.mark.asyncio
async def test_nexus_rounds_errors_use_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)):
        app._handle_textual_slash_command("/rounds abc")

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/rounds"
        assert result.title == "라운드"
        assert result.body == "숫자가 올바르지 않습니다."
        assert result.action_hint == "`/rounds <1..20>`를 사용하세요."
        assert result.severity == "warning"

        app._handle_textual_slash_command("/rounds 21")

        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/rounds"
        assert result.title == "라운드"
        assert result.body == "라운드는 1에서 20 사이여야 합니다."
        assert result.action_hint == "`/rounds <1..20>`를 사용하세요."
        assert result.severity == "warning"


@pytest.mark.asyncio
async def test_nexus_agent_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController()
    config = TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    app = TrinityTextualApp(config, controller)

    async with app.run_test(size=(120, 40)):
        app._handle_textual_slash_command("/agent")

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/agent"
        assert result.title == "에이전트"
        assert result.body.startswith("현재 에이전트 세션 설정입니다.")
        assert result.table_columns == ("에이전트", "활성화", "프로바이더")
        assert result.action_hint == "`/agent <name> on|off`로 에이전트 하나를 변경하세요."
        assert any(row[0] == "claude" and row[1] == "예" for row in result.table_rows)

        app._handle_textual_slash_command("/agent claude off")

        result = app.active_snapshot.local_commands[-1]
        assert config.agents["claude"].enabled is False
        assert result.command == "/agent"
        assert result.title == "에이전트"
        assert result.body.startswith(
            "이 세션에서 에이전트 `claude`를 비활성화했습니다."
        )
        assert any(row[0] == "claude" and row[1] == "아니오" for row in result.table_rows)


@pytest.mark.asyncio
async def test_nexus_agent_errors_use_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)):
        app._handle_textual_slash_command("/agent claude")

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/agent"
        assert result.title == "에이전트"
        assert result.body == "사용법: `/agent <name> on|off`"
        assert result.table_columns == ("에이전트", "활성화", "프로바이더")
        assert result.severity == "warning"

        app._handle_textual_slash_command("/agent missing on")

        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/agent"
        assert result.title == "에이전트"
        assert result.body == "알 수 없는 에이전트: `missing`"
        assert result.table_columns == ("에이전트", "활성화", "프로바이더")
        assert result.severity == "warning"

        app._handle_textual_slash_command("/agent claude maybe")

        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/agent"
        assert result.title == "에이전트"
        assert result.body == "사용법: `/agent <name> on|off`"
        assert result.severity == "warning"


@pytest.mark.asyncio
async def test_nexus_caveman_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController()
    config = TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    app = TrinityTextualApp(config, controller)

    async with app.run_test(size=(120, 40)):
        app._handle_textual_slash_command("/caveman")

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/caveman"
        assert result.title == "간결 모드"
        assert result.body.startswith("간결 모드:")
        assert result.table_columns == ("항목", "값")
        expected_mode = "on" if config.caveman_mode else "off"
        assert ("모드", expected_mode) in result.table_rows
        assert ("강도", config.caveman_intensity) in result.table_rows
        assert result.action_hint == "`/caveman <mode>`로 이 세션의 값을 변경하세요."

        app._handle_textual_slash_command("/caveman lite")

        result = app.active_snapshot.local_commands[-1]
        assert config.caveman_mode is True
        assert config.caveman_intensity == "lite"
        assert result.command == "/caveman"
        assert result.title == "간결 모드"
        assert result.body.startswith(
            "이 세션의 간결 모드를 `on` (`lite`)로 설정했습니다."
        )
        assert ("모드", "on") in result.table_rows
        assert ("강도", "lite") in result.table_rows


@pytest.mark.asyncio
async def test_nexus_caveman_error_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)):
        app._handle_textual_slash_command("/caveman strange")

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/caveman"
        assert result.title == "간결 모드"
        assert result.body == "사용법: /caveman [on|off|lite|full|ultra]"
        assert result.action_hint == "허용 모드: on, off, lite, full, ultra."
        assert result.severity == "warning"


@pytest.mark.asyncio
async def test_nexus_resume_answer_and_execute_errors_record_local_results(
    tmp_path,
) -> None:
    controller = FakeWorkflowController()
    controller.execution_outcome = TextualWorkflowOutcome(
        controller.current_snapshot,
        message="No blueprint is ready. Finish planning before execution.",
    )
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        for command in ("/resume", "/answer", "/execute"):
            app._handle_textual_slash_command(command)
            await pilot.pause()
            result = app.active_snapshot.local_commands[-1]
            assert result.command == command
            assert result.empty is True

        assert controller.started_prompts == []
        assert controller.follow_ups == []
        assert controller.execution_requests == 1


@pytest.mark.asyncio
async def test_nexus_execute_error_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController()
    controller.execution_outcome = TextualWorkflowOutcome(
        controller.current_snapshot,
        message="No blueprint is ready. Finish planning before execution.",
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)):
        app._handle_textual_slash_command("/execute")

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/execute"
        assert result.title == "실행"
        assert result.body == "준비된 설계안이 없습니다. 실행 전에 계획을 완료하세요."
        assert result.action_hint == (
            "작업 패키지가 준비되면 Nexus에서 `/execute`를 실행하세요."
        )
        assert result.severity == "warning"
        assert result.empty is True


@pytest.mark.asyncio
async def test_nexus_execute_recovery_uses_korean_labels(tmp_path) -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-recovery",
        state="failed",
        execution_recovery=ExecutionRecoverySnapshot(
            state="interrupted",
            run_id="run-1",
            target_workspace="/workspace/app",
            running_packages=("WP-001",),
            retry_candidates=("WP-001",),
            done_packages=("WP-002",),
            last_event="provider exit",
        ),
    )
    controller = FakeWorkflowController(snapshot)
    controller.execution_outcome = TextualWorkflowOutcome(
        snapshot,
        message="Previous execution was interrupted.",
        execution_recovery_required=True,
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)):
        app._handle_textual_slash_command("/execute")

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/execute"
        assert result.title == "실행 복구"
        assert result.body.startswith("이전 실행이 중단되었습니다.")
        assert result.table_columns == ("항목", "값")
        assert ("실행", "중단") in result.table_rows
        assert ("재시도 후보", "WP-001") in result.table_rows
        assert result.action_hint == (
            "`/execute-retry`, `/execute mark-interrupted`, "
            "`/execute abort` 중 하나를 실행하세요."
        )
        assert "###" not in result.body.splitlines()[0]
        assert "실행 복구" not in result.body.splitlines()[0]
        assert "- 실행: `중단`" in result.body


@pytest.mark.asyncio
async def test_nexus_answer_outcome_uses_korean_message(tmp_path) -> None:
    controller = FakeWorkflowController()
    controller.answer_outcome = TextualWorkflowOutcome(
        controller.current_snapshot,
        message="No matching workflow question: next",
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)):
        app._handle_textual_slash_command("/answer next 네")

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/answer"
        assert result.title == "답변"
        assert result.body == "일치하는 워크플로우 질문이 없습니다: next"
        assert result.severity == "warning"
        assert result.empty is True


@pytest.mark.asyncio
async def test_nexus_resume_outcome_uses_korean_message(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._handle_textual_slash_command("/resume latest")
        await pilot.pause()

        assert app.active_snapshot is not None
        result = next(
            item
            for item in app.active_snapshot.local_commands
            if item.command == "/resume"
        )
        assert result.command == "/resume"
        assert result.title == "재개"
        assert result.body == "워크플로우를 재개했습니다: wf-resumed-latest."
        assert result.severity == "info"
        assert result.empty is False


@pytest.mark.asyncio
async def test_nexus_unknown_slash_suggests_close_commands(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._handle_textual_slash_command("/stats")
        await pilot.pause()

        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/stats"
        assert result.title == "Unknown Command"
        assert any(row[0] == "/status" for row in result.table_rows)
        assert "/status" in result.body
        assert controller.started_prompts == []
        assert controller.follow_ups == []


@pytest.mark.asyncio
async def test_nexus_unknown_command_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._handle_textual_slash_command("/stats")
        await pilot.pause()

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/stats"
        assert result.title == "알 수 없는 명령"
        assert result.table_columns == ("추천", "요약")
        assert any(row[0] == "/status" for row in result.table_rows)
        assert "`/stats`은 Trinity 슬래시 명령이 아닙니다." in result.body
        assert "다음 명령을 찾으셨나요:" in result.body


@pytest.mark.asyncio
async def test_nexus_syntax_error_uses_korean_title(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)):
        app._handle_textual_slash_command('/ask "unterminated')

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == '/ask "unterminated'
        assert result.title == "구문 오류"
        assert result.severity == "warning"


@pytest.mark.asyncio
async def test_start_quit_slash_uses_confirmation_modal(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)

        composer = screen.query_one(PromptComposer)
        composer.set_text("/quit")
        composer.action_submit()
        await pilot.pause()

        assert isinstance(app.screen, ConfirmQuitModal)
        assert controller.started_prompts == []
        app.screen.query_one("#cancel-quit", Button).press()
        await pilot.pause()

        assert app.current_route == "start"
        assert isinstance(app.screen, StartScreen)


@pytest.mark.asyncio
async def test_start_quit_modal_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController()
    controller.is_running = True
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)) as pilot:
        composer = app.screen.query_one(PromptComposer)
        composer.set_text("/quit")
        composer.action_submit()
        await pilot.pause()

        assert isinstance(app.screen, ConfirmQuitModal)
        assert str(app.screen.query_one("#confirm-quit-title", Static).content) == (
            "Trinity 종료"
        )
        assert "워크플로우가 아직 실행 중입니다." in str(
            app.screen.query_one("#confirm-quit-body", Static).content
        )
        assert "Textual" not in str(
            app.screen.query_one("#confirm-quit-body", Static).content
        )
        assert str(app.screen.query_one("#cancel-quit", Button).label) == "취소"
        assert str(app.screen.query_one("#confirm-quit", Button).label) == "종료"


@pytest.mark.asyncio
async def test_nexus_context_without_session_records_empty_message(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)

        composer = screen.query_one("#nexus-composer", PromptComposer)
        composer.set_text("/context ")
        composer.action_submit()
        await pilot.pause()

        assert controller.follow_ups == []
        assert screen.follow_ups == []
        assert composer.text == ""
        central = screen.query_one(CentralAgentView)
        assert central.snapshot is not None
        result = central.snapshot.local_commands[-1]
        assert result.command == "/context"
        assert result.title == "Context"
        assert "No current session context" in result.body


@pytest.mark.asyncio
async def test_nexus_context_without_session_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._handle_textual_slash_command("/context")
        await pilot.pause()

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/context"
        assert result.title == "컨텍스트"
        assert result.body == (
            "현재 세션 컨텍스트가 없습니다. 먼저 프롬프트를 시작하거나 워크플로우를 재개하세요."
        )


@pytest.mark.asyncio
async def test_nexus_exact_context_enter_executes_without_palette_accept(
    tmp_path,
) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)

        composer = screen.query_one("#nexus-composer", PromptComposer)
        composer.set_text("/context")
        composer.focus_text_area()
        await pilot.press("enter")
        await pilot.pause()

        assert controller.follow_ups == []
        assert screen.follow_ups == []
        assert composer.text == ""
        central = screen.query_one(CentralAgentView)
        assert central.snapshot is not None
        result = central.snapshot.local_commands[-1]
        assert result.command == "/context"
        assert "No current session context" in result.body


@pytest.mark.asyncio
async def test_nexus_context_with_session_uses_korean_title(tmp_path) -> None:
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            session_id="wf-current",
            goal="현재 목표",
            state="blueprint_ready",
        )
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)):
        app._handle_textual_slash_command("/context")

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/context"
        assert result.title == "컨텍스트"
        assert "- 워크플로우: `wf-current`" in result.body
        assert "- 목표: 현재 목표" in result.body


@pytest.mark.asyncio
async def test_nexus_memory_uses_korean_title_and_columns(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._handle_textual_slash_command("/memory")
        await pilot.pause()

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/memory"
        assert result.title == "메모리 통계"
        assert result.table_columns == ("항목", "값")


@pytest.mark.asyncio
async def test_nexus_memory_cleanup_error_uses_korean_message(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._handle_textual_slash_command("/memory cleanup --keep-latest nope")
        await pilot.pause()

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/memory"
        assert result.title == "메모리 정리"
        assert result.body == "`--keep-latest`에는 숫자를 입력하세요."
        assert result.severity == "warning"


@pytest.mark.asyncio
async def test_nexus_local_command_notify_uses_korean_title(
    tmp_path,
    monkeypatch,
) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )
    notifications: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        app,
        "notify",
        lambda message, **kwargs: notifications.append(
            (message, str(kwargs.get("title", "")), str(kwargs.get("severity", "info")))
        ),
    )

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._handle_textual_slash_command("/memory")
        await pilot.pause()

        assert ("메모리 통계", "슬래시 명령", "information") in notifications


@pytest.mark.asyncio
async def test_nexus_artifact_usage_uses_korean_message(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._handle_textual_slash_command("/artifact")
        await pilot.pause()

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/artifact"
        assert result.title == "아티팩트"
        assert result.body == "사용법: `/artifact <memory-id>`"
        assert result.severity == "warning"


@pytest.mark.asyncio
async def test_nexus_artifact_body_uses_korean_labels(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    engine = engine_from_config(config)
    engine.initialize("Build app", ["codex"])
    engine.append_task_result(
        package_id="WP-001",
        agent="codex",
        status="done",
        summary="Implemented endpoint.",
    )
    record_id = engine.memory_store.recent(limit=1)[0].id if engine.memory_store else ""
    app = TrinityTextualApp(config, FakeWorkflowController())

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._handle_textual_slash_command(f"/artifact {record_id}")
        await pilot.pause()

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/artifact"
        assert result.title == "아티팩트"
        assert "## 아티팩트" in result.body
        assert "- 작업 패키지:" in result.body
        assert "### 요약" in result.body


@pytest.mark.asyncio
async def test_nexus_context_uses_current_snapshot_not_shared_file(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    SharedContextEngine(config.shared_context_path).write(
        "# Shared Context\n\n## Agreed Conclusion\nOld session summary.\n"
    )
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            session_id="wf-current",
            goal="Current session goal",
            state="blueprint_ready",
            synthesis=SynthesisSnapshot(
                summary="Current session summary.",
                consensus_progress="blueprint ready",
            ),
            decisions=["Use the current session only."],
        )
    )
    app = TrinityTextualApp(config, controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)

        composer = screen.query_one("#nexus-composer", PromptComposer)
        composer.set_text("/context ")
        composer.action_submit()
        await pilot.pause()

        assert controller.follow_ups == []
        central = screen.query_one(CentralAgentView)
        assert central.snapshot is not None
        result = central.snapshot.local_commands[-1]
        assert result.command == "/context"
        assert "Current session goal" in result.body
        assert "Current session summary." in result.body
        assert "Use the current session only." in result.body
        assert "Old session summary." not in result.body


@pytest.mark.asyncio
async def test_textual_session_setting_commands_are_local_session_only_results(
    tmp_path,
) -> None:
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            providers=[
                ProviderSnapshot(
                    name="claude",
                    provider="claude-code",
                    enabled=True,
                    status="Queued",
                    readiness="unknown",
                )
            ]
        )
    )
    config = TrinityConfig.default_config(project_dir=tmp_path)
    app = TrinityTextualApp(config, controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._handle_textual_slash_command("/rounds 7")
        await pilot.pause()
        assert config.max_deliberation_rounds == 7
        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/rounds"
        assert result.title == "Rounds"
        assert "for this session only" in result.body
        assert SESSION_ONLY_SETTING_NOTICE in result.body

        app._handle_textual_slash_command("/agent claude off")
        await pilot.pause()
        assert config.agents["claude"].enabled is False
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/agent"
        assert result.title == "Agent"
        assert SESSION_ONLY_SETTING_NOTICE in result.body

        app._handle_textual_slash_command("/caveman lite")
        await pilot.pause()
        assert config.caveman_mode is True
        assert config.caveman_intensity == "lite"
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/caveman"
        assert result.title == "Caveman"
        assert SESSION_ONLY_SETTING_NOTICE in result.body

        assert controller.started_prompts == []
        assert controller.follow_ups == []


@pytest.mark.asyncio
async def test_nexus_questions_select_uses_local_question_ui(tmp_path) -> None:
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            session_id="wf-fake",
            goal="game",
            state="needs_user_decision",
            questions=[
                QuestionSnapshot(
                    id="q-1",
                    question="Theme?",
                    options=["dark", "light"],
                )
            ],
        )
    )
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)

        composer = screen.query_one("#nexus-composer", PromptComposer)
        composer.set_text("/questions --select")
        composer.action_submit()
        await pilot.pause()

        assert controller.follow_ups == []
        assert screen.follow_ups == []
        central = screen.query_one(CentralAgentView)
        assert central.snapshot is not None
        assert central.snapshot.local_commands[-1].command == "/questions"
        assert "Use the option buttons in the question panel" in (
            central.snapshot.local_commands[-1].body
        )
        assert screen.query_one(QuestionPanel).query_one("#answer-q-1-1")


@pytest.mark.asyncio
async def test_nexus_questions_select_uses_korean_local_copy(tmp_path) -> None:
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            session_id="wf-fake",
            goal="game",
            state="needs_user_decision",
            questions=[
                QuestionSnapshot(
                    id="q-1",
                    question="Theme?",
                    options=["dark", "light"],
                )
            ],
        )
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)

        composer = screen.query_one("#nexus-composer", PromptComposer)
        composer.set_text("/questions --select")
        composer.action_submit()
        await pilot.pause()

        central = screen.query_one(CentralAgentView)
        assert central.snapshot is not None
        result = central.snapshot.local_commands[-1]
        assert result.command == "/questions"
        assert "선택된 질문: **q-1**" in result.body
        assert "질문 패널의 선택지 버튼" in result.body
        assert result.table_columns == ("ID", "상태", "질문", "선택지")


@pytest.mark.asyncio
async def test_nexus_slash_answer_option_routes_to_controller(tmp_path) -> None:
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            session_id="wf-fake",
            goal="game",
            state="needs_user_decision",
            questions=[
                QuestionSnapshot(
                    id="q-1",
                    question="Theme?",
                    options=["dark", "light"],
                )
            ],
        )
    )
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)

        composer = screen.query_one("#nexus-composer", PromptComposer)
        composer.set_text("/answer 1")
        composer.action_submit()
        await pilot.pause()

        assert controller.follow_ups == []
        assert controller.option_answers == [("1", "next", False)]
        assert screen.follow_ups == []


@pytest.mark.asyncio
async def test_start_slash_answer_without_args_uses_korean_usage(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(100, 30)):
        app._handle_textual_slash_command("/answer")

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/answer"
        assert result.title == "답변"
        assert result.body == "사용법: /answer <question-id|index|next> <answer>"
        assert result.action_hint == (
            "먼저 `/questions`를 실행해 대기 중인 질문을 확인하세요."
        )
        assert result.empty is True
        assert result.severity == "warning"


@pytest.mark.asyncio
async def test_start_slash_answer_replace_only_uses_korean_usage(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(100, 30)):
        app._handle_textual_slash_command("/answer --replace")

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/answer"
        assert result.title == "답변"
        assert result.body == "사용법: /answer <question-id|index|next> <answer>"
        assert result.action_hint.startswith("먼저 `/questions`")


@pytest.mark.asyncio
async def test_nexus_slash_resume_routes_to_controller(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)

        composer = screen.query_one("#nexus-composer", PromptComposer)
        composer.set_text("/resume latest")
        composer.action_submit()
        await pilot.pause()

        assert controller.follow_ups == []
        assert controller.resumes == ["latest"]
        assert app.active_snapshot is not None
        assert app.active_snapshot.session_id == "wf-resumed-latest"
        assert screen.snapshot is not None
        assert screen.snapshot.session_id == "wf-resumed-latest"
        assert screen.query_one(CentralAgentView).snapshot is not None
        assert screen.query_one(CentralAgentView).snapshot.session_id == "wf-resumed-latest"
        resume_result = _local_command(app.active_snapshot, "/resume")
        assert resume_result.title == "Resume"
        assert ("Workflow", "wf-resumed-latest") in resume_result.table_rows
        context_result = _local_command(app.active_snapshot, "/context")
        assert context_result.title == "Context"
        assert "wf-resumed-latest" in context_result.body


@pytest.mark.asyncio
async def test_start_slash_resume_picker_selection_switches_to_nexus(tmp_path) -> None:
    controller = FakeWorkflowController()
    controller.resume_options = [
        TextualWorkflowArchiveOption(
            selector="1",
            session_id="wf-archived",
            goal="archived goal",
            state="blueprint_ready",
            updated_at=1000.0,
        )
    ]
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        assert isinstance(app.screen, StartScreen)

        composer = app.screen.query_one(PromptComposer)
        composer.set_text("/resume")
        composer.action_submit()
        await pilot.pause()

        assert isinstance(app.screen, ResumeWorkflowPicker)
        app.screen.query_one("#resume-archive-1", Button).press()
        await pilot.pause()
        await pilot.pause()

        assert controller.started_prompts == []
        assert controller.follow_ups == []
        assert controller.resumes == ["1"]
        assert app.current_route == "nexus"
        assert isinstance(app.screen, NexusScreen)
        assert app.active_snapshot is not None
        assert app.active_snapshot.session_id == "wf-resumed-1"
        assert app.screen.snapshot is not None
        assert app.screen.snapshot.session_id == "wf-resumed-1"
        central = app.screen.query_one(CentralAgentView)
        assert central.snapshot is not None
        assert central.snapshot.session_id == "wf-resumed-1"
        resume_result = _local_command(app.active_snapshot, "/resume")
        assert resume_result.title == "Resume"
        assert ("Workflow", "wf-resumed-1") in resume_result.table_rows
        context_result = _local_command(app.active_snapshot, "/context")
        assert context_result.title == "Context"
        assert "wf-resumed-1" in context_result.body


@pytest.mark.asyncio
async def test_resume_picker_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController()
    controller.resume_options = [
        TextualWorkflowArchiveOption(
            selector="1",
            session_id="wf-ko",
            goal="한국어 세션",
            state="blueprint_ready",
            updated_at=1000.0,
        )
    ]
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)) as pilot:
        composer = app.screen.query_one(PromptComposer)
        composer.set_text("/resume")
        composer.action_submit()
        await pilot.pause()

        assert isinstance(app.screen, ResumeWorkflowPicker)
        assert str(app.screen.query_one("#resume-picker-title", Static).content) == (
            "워크플로우 재개"
        )
        assert str(app.screen.query_one("#cancel-resume-picker", Button).label) == "취소"
        archive_label = str(app.screen.query_one("#resume-archive-1", Button).label)
        assert "wf-ko" in archive_label
        assert "[설계 준비]" in archive_label
        assert "blueprint_ready" not in archive_label


def test_resume_picker_archive_label_uses_korean_empty_goal() -> None:
    archive = TextualWorkflowArchiveOption(
        selector="1",
        session_id="wf-empty-goal",
        goal="",
        state="done",
        updated_at=1000.0,
    )
    picker = ResumeWorkflowPicker([archive], lang="ko")

    label = picker._archive_label(archive)

    assert "[완료]" in label
    assert "(목표 없음)" in label
    assert "(no goal)" not in label


@pytest.mark.asyncio
async def test_resume_picker_arrow_keys_select_archive(tmp_path) -> None:
    controller = FakeWorkflowController()
    controller.resume_options = [
        TextualWorkflowArchiveOption(
            selector="1",
            session_id="wf-first",
            goal="first goal",
            state="blueprint_ready",
            updated_at=1000.0,
        ),
        TextualWorkflowArchiveOption(
            selector="2",
            session_id="wf-second",
            goal="second goal",
            state="needs_user_decision",
            updated_at=2000.0,
        ),
    ]
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        composer = app.screen.query_one(PromptComposer)
        composer.set_text("/resume")
        composer.action_submit()
        await pilot.pause()

        assert isinstance(app.screen, ResumeWorkflowPicker)
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()

        assert controller.resumes == ["2"]
        assert app.current_route == "nexus"
        assert app.active_snapshot is not None
        assert app.active_snapshot.session_id == "wf-resumed-2"
        context_result = _local_command(app.active_snapshot, "/context")
        assert "wf-resumed-2" in context_result.body


@pytest.mark.asyncio
async def test_resume_picker_arrow_keys_scroll_long_archive_list(tmp_path) -> None:
    controller = FakeWorkflowController()
    controller.resume_options = [
        TextualWorkflowArchiveOption(
            selector=str(index),
            session_id=f"wf-{index:02d}",
            goal=f"archived goal {index}",
            state="blueprint_ready",
            updated_at=1000.0 + index,
        )
        for index in range(1, 31)
    ]
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(100, 24)) as pilot:
        composer = app.screen.query_one(PromptComposer)
        composer.set_text("/resume")
        composer.action_submit()
        await pilot.pause()

        assert isinstance(app.screen, ResumeWorkflowPicker)
        archive_list = app.screen.query_one("#resume-archive-list", VerticalScroll)
        assert archive_list.scroll_y == 0

        for _ in range(18):
            await pilot.press("down")
        await pilot.pause()

        assert app.screen.selected_index == 18
        assert archive_list.scroll_y > 0


@pytest.mark.asyncio
async def test_nexus_slash_resume_without_selector_opens_archive_picker(tmp_path) -> None:
    controller = FakeWorkflowController()
    controller.resume_options = [
        TextualWorkflowArchiveOption(
            selector="1",
            session_id="wf-archived",
            goal="archived goal",
            state="blueprint_ready",
            updated_at=1000.0,
        )
    ]
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)

        composer = screen.query_one("#nexus-composer", PromptComposer)
        composer.set_text("/resume ")
        composer.action_submit()
        await pilot.pause()

        assert controller.follow_ups == []
        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/resume"
        assert result.table_columns == ("Selector", "Workflow", "State", "Goal")
        assert result.table_rows[0][:3] == ("1", "wf-archived", "blueprint_ready")
        assert isinstance(app.screen, ResumeWorkflowPicker)
        button = app.screen.query_one("#resume-archive-1", Button)
        button.press()
        await pilot.pause()

        assert controller.resumes == ["1"]
        assert app.active_snapshot is not None
        assert app.active_snapshot.session_id == "wf-resumed-1"
        resume_result = _local_command(app.active_snapshot, "/resume")
        assert ("Workflow", "wf-resumed-1") in resume_result.table_rows
        context_result = _local_command(app.active_snapshot, "/context")
        assert "wf-resumed-1" in context_result.body


@pytest.mark.asyncio
async def test_nexus_slash_resume_picker_cancel_records_result(tmp_path) -> None:
    controller = FakeWorkflowController()
    controller.resume_options = [
        TextualWorkflowArchiveOption(
            selector="1",
            session_id="wf-archived",
            goal="archived goal",
            state="blueprint_ready",
            updated_at=1000.0,
        )
    ]
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._handle_textual_slash_command("/resume")
        await pilot.pause()
        assert isinstance(app.screen, ResumeWorkflowPicker)

        app.screen.query_one("#cancel-resume-picker", Button).press()
        await pilot.pause()

        assert controller.resumes == []
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/resume"
        assert "cancelled" in result.body
        assert result.empty is True


@pytest.mark.asyncio
async def test_nexus_resume_without_archives_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)):
        app._handle_textual_slash_command("/resume")

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/resume"
        assert result.title == "재개"
        assert result.body == "재개할 저장된 워크플로우가 없습니다."
        assert result.action_hint == (
            "`/resume`을 사용하려면 먼저 워크플로우를 시작하고 보관하세요."
        )
        assert result.empty is True


@pytest.mark.asyncio
async def test_nexus_resume_archive_picker_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController()
    controller.resume_options = [
        TextualWorkflowArchiveOption(
            selector="1",
            session_id="wf-archived",
            goal="",
            state="blueprint_ready",
            updated_at=1000.0,
        )
    ]
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)) as pilot:
        app._handle_textual_slash_command("/resume")
        await pilot.pause()

        assert app.active_snapshot is not None
        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/resume"
        assert result.title == "재개"
        assert result.body.startswith("재개할 수 있는 저장된 워크플로우")
        assert result.table_columns == ("선택자", "워크플로우", "상태", "목표")
        assert result.table_rows[0] == ("1", "wf-archived", "설계 준비", "(목표 없음)")
        assert result.action_hint == "재개 모달에서 워크플로우를 선택하세요."
        assert isinstance(app.screen, ResumeWorkflowPicker)

        app.screen.query_one("#cancel-resume-picker", Button).press()
        await pilot.pause()

        result = app.active_snapshot.local_commands[-1]
        assert result.command == "/resume"
        assert result.title == "재개"
        assert result.body == "재개 선택을 취소했습니다."
        assert result.action_hint == (
            "보관된 워크플로우를 선택하려면 `/resume`을 다시 실행하세요."
        )


@pytest.mark.asyncio
async def test_nexus_resume_success_uses_korean_labels(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(120, 40)) as pilot:
        app._handle_textual_slash_command("/resume latest")
        await pilot.pause()

        assert app.active_snapshot is not None
        assert app.active_snapshot.session_id == "wf-resumed-latest"
        result = _local_command(app.active_snapshot, "/resume")
        assert result.title == "재개"
        assert result.table_columns == ("항목", "값")
        assert ("워크플로우", "wf-resumed-latest") in result.table_rows
        assert ("상태", "설계 준비") in result.table_rows
        assert ("라운드", "0") in result.table_rows


@pytest.mark.asyncio
async def test_prompt_composer_shows_slash_command_palette(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(100, 30)) as pilot:
        composer = app.screen.query_one(PromptComposer)

        composer.set_text("/")
        await pilot.pause()
        palette = composer.query_one("#prompt-command-palette")
        options = [str(option.content) for option in composer.query(".command-option")]

        assert palette.display is True
        assert any("/status" in option for option in options)

        composer.set_text("/ex")
        await pilot.pause()
        filtered_options = [str(option.content) for option in composer.query(".command-option")]

        assert any("/execute" in option for option in filtered_options)

        composer.set_text("/rep")
        await pilot.pause()
        report_options = [str(option.content) for option in composer.query(".command-option")]

        assert any("/report" in option for option in report_options)

        composer.set_text("/q")
        await pilot.pause()
        quit_options = [str(option.content) for option in composer.query(".command-option")]

        assert any("/q" in option for option in quit_options)
        assert any("/quit" in option for option in quit_options)

        composer.set_text("hello /status")
        await pilot.pause()
        assert palette.display is False


@pytest.mark.asyncio
async def test_prompt_composer_localizes_slash_command_palette_in_korean(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path, lang="ko"))

    async with app.run_test(size=(100, 30)) as pilot:
        composer = app.screen.query_one(PromptComposer)

        composer.set_text("/")
        await pilot.pause()
        options = [str(option.content) for option in composer.query(".command-option")]
        more = str(composer.query_one("#command-option-more").content)

        assert any("/status" in option for option in options)
        assert any("제공자와 워크플로우 상태 보기" in option for option in options)
        assert not any("show provider and workflow status" in option for option in options)
        assert "명령 더 있음" in more

        composer.set_text("/missing")
        await pilot.pause()

        empty = str(composer.query_one("#command-option-0").content)
        assert empty == "일치하는 명령이 없습니다"


@pytest.mark.asyncio
async def test_nexus_composer_uses_configured_slash_command_language(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path, lang="ko"))

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)

        composer = screen.query_one("#nexus-composer", PromptComposer)
        composer.set_text("/ex")
        await pilot.pause()

        options = [str(option.content) for option in composer.query(".command-option")]

        assert any("/execute" in option for option in options)
        assert any("실행 사전 점검 열기" in option for option in options)
        assert not any("open execution preflight" in option for option in options)


@pytest.mark.asyncio
async def test_screen_and_composer_bindings_use_configured_language(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path, lang="ko"))

    async with app.run_test(size=(120, 40)) as pilot:
        start = app.screen
        assert isinstance(start, StartScreen)
        assert _binding_description(start._bindings, "ctrl+enter", "submit") == "보내기"

        composer = start.query_one(PromptComposer)
        textarea = composer.query_one(ComposerTextArea)
        assert _binding_description(composer._bindings, "enter", "submit") == "보내기"
        assert _binding_description(textarea._bindings, "shift+enter", "insert_newline") == "새 줄"

        app.switch_to("nexus")
        await pilot.pause()
        nexus = app.screen
        assert isinstance(nexus, NexusScreen)
        assert _binding_description(nexus._bindings, "ctrl+e", "request_execute") == "실행"


@pytest.mark.asyncio
async def test_start_and_central_chrome_uses_korean_labels(
    tmp_path,
    monkeypatch,
) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path, lang="ko"))
    notifications: list[tuple[str, str]] = []
    monkeypatch.setattr(
        app,
        "notify",
        lambda message, **kwargs: notifications.append(
            (message, str(kwargs.get("severity", "info")))
        ),
    )

    async with app.run_test(size=(120, 40)) as pilot:
        start = app.screen
        assert isinstance(start, StartScreen)
        with pytest.raises(NoMatches):
            start.query_one("#start-subtitle", Static)
        assert str(start.query_one("#workspace-candidate", Static).content).startswith(
            "계획 대상: "
        )
        start.set_workspace_candidate(None)
        assert str(start.query_one("#workspace-candidate", Static).content) == (
            "대상 작업 폴더 없음"
        )

        composer = start.query_one(PromptComposer)
        assert composer.placeholder == "Trinity가 무엇을 진행하면 될까요?"
        text_area = composer.query_one(ComposerTextArea)
        text_area.blur()
        await pilot.pause()
        assert text_area.placeholder == "Trinity가 무엇을 진행하면 될까요?"

        selector = start.query_one(AgentRecipientModelSelector)
        selector.set_selected_agents(())
        composer.set_text("작업해줘")
        composer.action_submit()
        await pilot.pause()
        assert notifications[-1] == ("에이전트를 하나 이상 선택하세요.", "warning")

        app.switch_to("nexus")
        await pilot.pause()
        nexus = app.screen
        assert isinstance(nexus, NexusScreen)
        assert str(nexus.query_one("#central-title", Static).content) == (
            "중앙 에이전트"
        )


@pytest.mark.asyncio
async def test_prompt_composer_hides_placeholder_while_focused_for_ime_preedit(
    tmp_path,
) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(100, 30)) as pilot:
        composer = app.screen.query_one(PromptComposer)
        text_area = composer.query_one(ComposerTextArea)
        await pilot.pause()

        assert text_area.has_focus is True
        assert text_area.placeholder == ""

        text_area.blur()
        await pilot.pause()
        assert text_area.placeholder == "What should Trinity work on?"

        text_area.focus()
        await pilot.pause()
        assert text_area.placeholder == ""


@pytest.mark.asyncio
async def test_prompt_composer_modified_enter_inserts_newline(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(100, 30)) as pilot:
        composer = app.screen.query_one(PromptComposer)
        composer.set_text("line one")
        composer.focus_text_area()

        await pilot.press("shift+enter")
        await pilot.pause()

        await pilot.press("ctrl+j")
        await pilot.pause()

        assert app.current_route == "start"
        assert composer.text == "line one\n\n"


@pytest.mark.asyncio
async def test_prompt_composer_summarizes_large_paste_for_display(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(100, 30)):
        composer = app.screen.query_one(PromptComposer)
        text_area = composer.query_one(TextArea)
        pasted = "a" * 1200

        await text_area._on_paste(events.Paste(pasted))

        assert composer.text == "[Pasted Content 1200 chars]"
        assert composer.submission_text == pasted


@pytest.mark.asyncio
async def test_prompt_composer_summarizes_large_paste_with_korean_placeholder(
    tmp_path,
) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path, lang="ko"))

    async with app.run_test(size=(100, 30)):
        composer = app.screen.query_one(PromptComposer)
        text_area = composer.query_one(TextArea)
        pasted = "가" * 1200

        await text_area._on_paste(events.Paste(pasted))

        assert composer.text == "[붙여넣은 콘텐츠 1200자]"
        assert composer.submission_text == pasted


@pytest.mark.asyncio
async def test_prompt_composer_arrow_selects_slash_command(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(100, 30)) as pilot:
        composer = app.screen.query_one(PromptComposer)
        composer.set_text("/")
        composer.focus_text_area()
        await pilot.pause()

        await pilot.press("down")
        await pilot.pause()
        selected = [str(option.content) for option in composer.query(".command-option-selected")]

        assert any("/context" in option for option in selected)

        await pilot.press("enter")
        await pilot.pause()
        assert app.current_route == "start"
        assert composer.text == "/context "


@pytest.mark.asyncio
async def test_prompt_composer_tab_accepts_slash_command(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(100, 30)) as pilot:
        composer = app.screen.query_one(PromptComposer)
        composer.set_text("/con")
        composer.focus_text_area()
        await pilot.pause()

        await pilot.press("tab")
        await pilot.pause()

        assert app.current_route == "start"
        assert composer.text == "/context "


@pytest.mark.asyncio
async def test_prompt_composer_tab_completes_exact_slash_without_running(
    tmp_path,
) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(100, 30)) as pilot:
        composer = app.screen.query_one(PromptComposer)
        composer.set_text("/context")
        composer.focus_text_area()
        await pilot.pause()

        await pilot.press("tab")
        await pilot.pause()

        assert app.current_route == "start"
        assert composer.text == "/context "
        assert controller.started_prompts == []
        assert controller.follow_ups == []
        assert app.active_snapshot is None


@pytest.mark.asyncio
async def test_prompt_composer_scrolls_slash_command_window(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(100, 30)) as pilot:
        composer = app.screen.query_one(PromptComposer)
        composer.set_text("/")
        composer.focus_text_area()
        await pilot.pause()

        for _ in range(COMMAND_LIMIT + 3):
            await pilot.press("down")
        await pilot.pause()

        selected = [str(option.content) for option in composer.query(".command-option-selected")]
        visible = [str(option.content) for option in composer.query(".command-option")]
        expected = COMMAND_SPECS[COMMAND_LIMIT + 3].name

        assert any(expected in option for option in selected)
        assert any(expected in option for option in visible)


@pytest.mark.asyncio
async def test_start_submission_uses_fresh_snapshot(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-previous",
            goal="old question",
            state=WorkflowState.NEEDS_USER_DECISION,
            active_agents=["claude"],
            current_round=1,
        )
    )
    response_dir = config.effective_state_dir / "responses" / "round-01"
    response_dir.mkdir(parents=True)
    (response_dir / "claude-round-1-claude-old.clean.txt").write_text(
        "previous answer",
        encoding="utf-8",
    )

    controller = FakeWorkflowController()
    app = TrinityTextualApp(config, controller)

    async with app.run_test(size=(100, 30)) as pilot:
        composer = app.screen.query_one(PromptComposer)
        composer.set_text("new question")
        composer.action_submit()
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, NexusScreen)
        assert screen.snapshot is not None
        assert screen.snapshot.goal == "new question"
        assert screen.snapshot.session_id != "wf-previous"
        assert all(provider.raw_output == "" for provider in screen.snapshot.providers)


@pytest.mark.asyncio
async def test_start_screen_shell_is_centered(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        shell = app.screen.query_one("#start-shell")
        left_margin = shell.region.x
        right_margin = app.screen.size.width - shell.region.right

        assert left_margin > 0
        assert abs(left_margin - right_margin) <= 1


@pytest.mark.asyncio
async def test_nexus_screen_renders_provider_panels(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        panels = app.screen.query(ProviderPanel)
        assert len(panels) == 3
        assert app.screen.query_one("#provider-claude", ProviderPanel).state.enabled is True
        assert app.screen.query_one("#provider-codex", ProviderPanel).state.enabled is False


@pytest.mark.asyncio
async def test_nexus_follow_up_stays_in_current_workflow(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, NexusScreen)
        composer = screen.query_one("#nexus-composer", PromptComposer)
        composer.set_text("이어서 검토해줘")
        composer.action_submit()
        await pilot.pause()

        assert app.current_route == "nexus"
        assert screen.follow_ups == ["이어서 검토해줘"]
        assert controller.follow_ups == ["이어서 검토해줘"]
        assert controller.follow_up_targets == [("claude",)]
        assert screen.snapshot is not None
        assert "follow-up: 이어서 검토해줘" in screen.snapshot.work_packages


@pytest.mark.asyncio
async def test_nexus_follow_up_syncs_visible_workspace_before_submit(tmp_path) -> None:
    controller = FakeWorkflowController()
    control_repo = tmp_path / "Trinity"
    target_workspace = tmp_path / "msu"
    control_repo.mkdir()
    target_workspace.mkdir()
    config = TrinityConfig.default_config(project_dir=control_repo)
    app = TrinityTextualApp(config, controller, launch_cwd=control_repo)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        app._set_workspace_candidate(target_workspace, sync_nexus=True)
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, NexusScreen)
        composer = screen.query_one("#nexus-composer", PromptComposer)
        composer.set_text("프로젝트를 분석해라.")
        composer.action_submit()
        await pilot.pause()

        assert controller.target_workspace == target_workspace
        assert controller.follow_up_workspaces == [target_workspace]
        assert controller.follow_ups == ["프로젝트를 분석해라."]


@pytest.mark.asyncio
async def test_nexus_follow_up_passes_selected_agents_and_models(tmp_path) -> None:
    controller = FakeWorkflowController()
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents["codex"].enabled = True
    app = TrinityTextualApp(config, controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, NexusScreen)
        selector = screen.query_one(AgentRecipientModelSelector)
        selector.set_selected_agents(("codex",))
        selector.set_model_overrides({"codex": "gpt-5"})

        composer = screen.query_one("#nexus-composer", PromptComposer)
        composer.set_text("코덱스만 다시 봐줘")
        composer.action_submit()
        await pilot.pause()

        assert controller.follow_ups == ["코덱스만 다시 봐줘"]
        assert controller.follow_up_targets == [("codex",)]
        assert controller.follow_up_models[-1]["codex"] == "gpt-5"


@pytest.mark.parametrize(
    ("button_label", "expected_prompt"),
    (
        ("기능 보강", "핵심 기능"),
        ("리스크 보강", "실행 리스크"),
        ("작업 재분배", "작업 패키지의 범위"),
    ),
)
@pytest.mark.asyncio
async def test_nexus_refine_buttons_pass_selected_agents_and_models(
    tmp_path,
    button_label: str,
    expected_prompt: str,
) -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-blueprint",
        goal="game",
        state="blueprint_ready",
        work_packages=["WP-001 codex: gameplay loop"],
    )
    controller = FakeWorkflowController(snapshot)
    config = TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    config.agents["codex"].enabled = True
    app = TrinityTextualApp(config, controller)

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, NexusScreen)
        screen.apply_snapshot(snapshot)
        selector = screen.query_one(AgentRecipientModelSelector)
        selector.set_selected_agents(("codex",))
        selector.set_model_overrides({"codex": "gpt-5"})
        await pilot.pause()

        central = screen.query_one(CentralAgentView)
        buttons = list(central.query("#central-actions Button"))
        refine_button = next(
            button for button in buttons if str(button.label) == button_label
        )
        refine_button.press()
        await pilot.pause()

        assert controller.follow_ups
        assert expected_prompt in controller.follow_ups[-1]
        assert controller.follow_up_targets == [("codex",)]
        assert controller.follow_up_models[-1] == {"codex": "gpt-5"}


@pytest.mark.asyncio
async def test_nexus_ask_slash_routes_targeted_follow_up(tmp_path) -> None:
    controller = FakeWorkflowController()
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents["codex"].enabled = True
    app = TrinityTextualApp(config, controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, NexusScreen)
        composer = screen.query_one("#nexus-composer", PromptComposer)
        composer.set_text("/ask codex --model gpt-5 다시 검토")
        composer.action_submit()
        await pilot.pause()

        assert controller.follow_ups == ["다시 검토"]
        assert controller.follow_up_targets == [("codex",)]
        assert controller.follow_up_models[-1] == {"codex": "gpt-5"}
        assert screen.follow_ups == []


@pytest.mark.asyncio
async def test_central_agent_view_renders_question_options(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)

        screen.apply_snapshot(
            WorkflowNexusSnapshot(
                session_id="wf-ui",
                goal="Build UI",
                state="needs_user_decision",
                questions=[
                    QuestionSnapshot(
                        id="q-1",
                        question="Theme?",
                        options=["dark", "light"],
                        recommended_option="dark",
                    )
                ],
            )
        )
        await pilot.pause()

        question_panel = screen.query_one(QuestionPanel)
        assert question_panel.query_one("#answer-q-1-1")
        assert question_panel.query_one("#answer-q-1-2")


@pytest.mark.asyncio
async def test_central_agent_view_renders_all_questions(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)

        screen.apply_snapshot(
            WorkflowNexusSnapshot(
                state="needs_user_decision",
                questions=[
                    QuestionSnapshot(
                        id="q-1",
                        question="Engine?",
                        options=["Godot", "Unity"],
                    ),
                    QuestionSnapshot(
                        id="q-2",
                        question="Monetization?",
                        options=["F2P", "Paid"],
                    ),
                ],
            )
        )
        await pilot.pause()

        question_panel = screen.query_one(QuestionPanel)
        assert "Questions for You (2)" in str(
            question_panel.query_one("#question-panel-title").content
        )
        assert question_panel.query_one("#answer-q-1-1")
        assert question_panel.query_one("#answer-q-1-2")
        assert question_panel.query_one("#answer-q-2-1")
        assert question_panel.query_one("#answer-q-2-2")
        rendered_questions = [
            str(item.content) for item in question_panel.query(".question-text")
        ]
        assert rendered_questions == [
            "1. [open] Engine?",
            "2. [open] Monetization?",
        ]


@pytest.mark.asyncio
async def test_central_agent_view_renders_local_command_tables(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)

        screen.apply_snapshot(
            WorkflowNexusSnapshot(
                local_commands=[
                    LocalCommandSnapshot(
                        command="/workflow",
                        title="Workflow",
                        body="- State: `blueprint_ready`",
                        table_columns=("Item", "Value"),
                        table_rows=(
                            ("State", "blueprint_ready"),
                            ("Work packages", "3"),
                        ),
                    )
                ]
            )
        )
        await pilot.pause()

        central = screen.query_one(CentralAgentView)
        table = central.query_one(".local-command-table", DataTable)

        assert table.row_count == 2
        assert table.show_cursor is False
        assert table.cursor_type == "none"
        assert "Command Result" in central.render_markdown()
        assert "Local Command Results" not in central.render_markdown()


@pytest.mark.asyncio
async def test_textual_status_refresh_replaces_existing_local_command_table(
    tmp_path,
) -> None:
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            providers=[
                ProviderSnapshot(
                    name="claude",
                    provider="claude-code",
                    enabled=True,
                    status="Queued",
                    readiness="unknown",
                )
            ]
        )
    )
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._handle_textual_slash_command("/status")
        await pilot.pause()
        app._handle_textual_slash_command("/status")
        await pilot.pause()
        app._handle_textual_slash_command("/status")
        await pilot.pause()

        assert controller.started_prompts == []
        assert controller.follow_ups == []
        assert app.active_snapshot is not None
        assert app.active_snapshot.local_commands[-1].command == "/status"
        assert any(
            value.endswith("readiness=not checked")
            for _, value in app.active_snapshot.local_commands[-1].table_rows
        )
        assert [command.command for command in app.active_snapshot.local_commands].count(
            "/status"
        ) == 1

        central = app.screen.query_one(CentralAgentView)
        tables = list(central.query(".local-command-table"))
        assert len(tables) == 1
        assert tables[-1].row_count > 0


@pytest.mark.asyncio
async def test_central_agent_view_keeps_answered_question_history(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)

        screen.apply_snapshot(
            WorkflowNexusSnapshot(
                state="blueprint_ready",
                questions=[
                    QuestionSnapshot(
                        id="q-1",
                        question="Engine?",
                        options=["Godot", "Unity"],
                        status="answered",
                        answer="Godot",
                    ),
                    QuestionSnapshot(
                        id="q-2",
                        question="Platform?",
                        options=["PC", "Mobile"],
                    ),
                ],
            )
        )
        await pilot.pause()

        question_panel = screen.query_one(QuestionPanel)
        assert "1. [answered] Engine?" in [
            str(item.content) for item in question_panel.query(".question-text")
        ]
        assert "Answer: Godot" in [
            str(item.content) for item in question_panel.query(".question-answer")
        ]
        assert not question_panel.query("#answer-q-1-1")
        assert question_panel.query_one("#answer-q-2-1")


@pytest.mark.asyncio
async def test_question_panel_localizes_korean_status_tokens(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path, lang="ko"))

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)

        screen.apply_snapshot(
            WorkflowNexusSnapshot(
                state="needs_user_decision",
                questions=[
                    QuestionSnapshot(
                        id="q-1",
                        question="엔진?",
                        options=["Godot", "Unity"],
                    ),
                    QuestionSnapshot(
                        id="q-2",
                        question="플랫폼?",
                        options=["PC", "Mobile"],
                        status="answered",
                        answer="PC",
                    ),
                ],
            )
        )
        await pilot.pause()

        question_panel = screen.query_one(QuestionPanel)
        rendered_questions = [
            str(item.content) for item in question_panel.query(".question-text")
        ]
        answers = [
            str(item.content) for item in question_panel.query(".question-answer")
        ]

        assert rendered_questions == [
            "1. [답변 대기] 엔진?",
            "2. [답변됨] 플랫폼?",
        ]
        assert "답변: PC" in answers


@pytest.mark.asyncio
async def test_central_agent_question_options_use_two_column_grid(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)
        screen.apply_snapshot(
            WorkflowNexusSnapshot(
                questions=[
                    QuestionSnapshot(
                        id="q-grid",
                        question="Direction?",
                        options=["match three plus story", "physics puzzle"],
                    )
                ],
            )
        )
        await pilot.pause()

        question_panel = screen.query_one(QuestionPanel)
        grid = question_panel.query_one(".question-options")
        buttons = list(grid.query("Button"))

        assert len(buttons) == 2
        assert grid.styles.layout.name == "grid"
        assert grid.styles.grid_size_columns == 2


@pytest.mark.asyncio
async def test_nexus_running_surfaces_show_activity(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)
        screen.apply_snapshot(
            WorkflowNexusSnapshot(
                state="deliberating",
                round_num=1,
                providers=[
                    ProviderSnapshot(
                        name="claude",
                        provider="claude-code",
                        enabled=True,
                        status="Running",
                    )
                ],
                synthesis=SynthesisSnapshot(
                    summary="Central agent is synthesizing round 1 provider responses.",
                    consensus_progress="round 1 synthesizing",
                    source="runtime",
                    status="running",
                ),
            )
        )
        screen.advance_activity_frame()
        await pilot.pause()

        panel = screen.query_one("#provider-claude", ProviderPanel)
        central = screen.query_one(CentralAgentView)
        assert panel.has_class("provider-running")
        assert panel.has_class("provider-state-running")
        assert "RUN" in str(panel.query_one(".provider-status").content)
        assert central.has_class("central-running")
        assert "Central Agent" in str(central.query_one("#central-title").content)
        assert "round 1 synthesizing" in central.render_markdown()


@pytest.mark.asyncio
async def test_nexus_activity_frame_skips_when_no_running_surfaces(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)
        screen.apply_snapshot(
            WorkflowNexusSnapshot(
                state="blueprint_ready",
                providers=[
                    ProviderSnapshot(
                        name="claude",
                        provider="claude-code",
                        enabled=True,
                        status="Ready",
                    )
                ],
            )
        )
        await pilot.pause()

        panel = screen.query_one("#provider-claude", ProviderPanel)
        central = screen.query_one(CentralAgentView)
        panel_frames: list[int] = []
        central_frames: list[int] = []
        original_panel_frame = panel.set_activity_frame
        original_central_frame = central.set_activity_frame

        def counted_panel_frame(frame: int) -> None:
            panel_frames.append(frame)
            original_panel_frame(frame)

        def counted_central_frame(frame: int) -> None:
            central_frames.append(frame)
            original_central_frame(frame)

        panel.set_activity_frame = counted_panel_frame
        central.set_activity_frame = counted_central_frame
        previous_frame = screen._activity_frame

        screen.advance_activity_frame()
        await pilot.pause()

        assert screen._activity_frame == previous_frame
        assert panel_frames == []
        assert central_frames == []


@pytest.mark.asyncio
async def test_nexus_provider_panel_marks_non_ok_response_as_issue(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)
        screen.apply_snapshot(
            WorkflowNexusSnapshot(
                providers=[
                    ProviderSnapshot(
                        name="claude",
                        provider="claude-code",
                        enabled=True,
                        status="Ready",
                        summary="[Error: exit code 1]",
                        response_status="invalid",
                    )
                ]
            )
        )
        await pilot.pause()

        panel = screen.query_one("#provider-claude", ProviderPanel)
        assert panel.has_class("provider-state-issue")
        assert "ISSUE" in str(panel.query_one(".provider-status").content)
        assert "[Error: exit code 1]" in str(
            panel.query_one(".provider-summary").content
        )


@pytest.mark.asyncio
async def test_nexus_provider_strip_stays_compact_on_small_viewport(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(80, 24)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)
        screen.apply_snapshot(
            WorkflowNexusSnapshot(
                providers=[
                    ProviderSnapshot(
                        name="claude",
                        provider="claude-code",
                        enabled=True,
                        status="Running",
                        actual_model="claude-opus-4.1",
                        context_window=200000,
                        budget_source="runtime_metadata",
                        session_id="claude-session-123456789",
                    ),
                    ProviderSnapshot(
                        name="codex",
                        provider="codex",
                        enabled=True,
                        status="Queued",
                        actual_model="gpt-5.5",
                        context_window=272000,
                        budget_source="local_cli_cache",
                        session_id="codex-session-123456789",
                        output_contract="execution_v1",
                    ),
                    ProviderSnapshot(
                        name="antigravity",
                        provider="antigravity",
                        enabled=True,
                        status="Ready",
                        actual_model="ag-high-context",
                        context_window=128000,
                        budget_source="trinity_config",
                        session_id="antigravity-session-123456789",
                    ),
                ]
            )
        )
        await pilot.pause()

        strip = screen.query_one("#provider-strip")
        panels = list(screen.query(ProviderPanel))

        assert strip.region.height == 5
        assert strip.has_class("provider-strip-3")
        assert len(panels) == 3
        for panel in panels:
            assert panel.region.height == 5
            assert panel.region.y >= strip.region.y
            assert (
                panel.region.y + panel.region.height
                <= strip.region.y + strip.region.height
            )
            assert str(panel.query_one(".provider-name").content)
            assert str(panel.query_one(".provider-status").content)
            assert str(panel.query_one(".provider-meta").content)
        assert "Antigravity" in str(
            screen.query_one("#provider-antigravity .provider-name").content
        )
        assert "out execution_v1" in str(
            screen.query_one("#provider-codex .provider-meta").content
        )


@pytest.mark.asyncio
async def test_nexus_provider_strip_uses_configured_provider_count(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents.pop("antigravity")
    app = TrinityTextualApp(config)

    async with app.run_test(size=(80, 24)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, NexusScreen)
        strip = screen.query_one("#provider-strip")
        panels = list(screen.query(ProviderPanel))

        assert strip.has_class("provider-strip-2")
        assert len(panels) == 2
        assert screen.query_one("#provider-claude", ProviderPanel)
        assert screen.query_one("#provider-codex", ProviderPanel)
        with pytest.raises(NoMatches):
            screen.query_one("#provider-antigravity", ProviderPanel)


@pytest.mark.asyncio
async def test_workflow_outcome_does_not_render_hidden_nexus(
    tmp_path,
    monkeypatch,
) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        nexus = app.get_screen("nexus", NexusScreen)
        calls: list[str] = []

        def counted_apply_snapshot(snapshot: WorkflowNexusSnapshot) -> None:
            calls.append(snapshot.session_id)

        monkeypatch.setattr(nexus, "apply_snapshot", counted_apply_snapshot)
        app._apply_workflow_outcome(
            TextualWorkflowOutcome(
                WorkflowNexusSnapshot(session_id="wf-hidden", state="reviewing"),
                running=True,
            )
        )
        await pilot.pause()

        assert app.current_route == "execution"
        assert app.active_snapshot is not None
        assert app.active_snapshot.session_id == "wf-hidden"
        assert calls == []


@pytest.mark.asyncio
async def test_switch_to_nexus_applies_snapshot_once(tmp_path, monkeypatch) -> None:
    snapshot = WorkflowNexusSnapshot(session_id="wf-once", state="reviewing")
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))
    app.active_snapshot = snapshot

    async with app.run_test(size=(120, 40)) as pilot:
        nexus = app.get_screen("nexus", NexusScreen)
        original_apply_snapshot = nexus.apply_snapshot
        calls: list[str] = []

        def counted_apply_snapshot(snapshot: WorkflowNexusSnapshot) -> None:
            calls.append(snapshot.session_id)
            original_apply_snapshot(snapshot)

        monkeypatch.setattr(nexus, "apply_snapshot", counted_apply_snapshot)
        app.switch_to("nexus")
        await pilot.pause()

        assert app.current_route == "nexus"
        assert calls == ["wf-once"]


@pytest.mark.asyncio
async def test_central_agent_view_skips_repeated_snapshot_rerender(
    tmp_path,
    monkeypatch,
) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-repeat",
        state="reviewing",
        goal="Build UI",
        decisions=["Use Textual"],
        work_packages=["WP-001 codex: UI shell (done)"],
    )

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)
        screen.apply_snapshot(snapshot)
        await pilot.pause()

        central = screen.query_one(CentralAgentView)
        markdown = central.query_one("#central-markdown", Markdown)
        original_update = markdown.update
        markdown_updates: list[str] = []

        def counted_update(content) -> None:
            markdown_updates.append(str(content))
            original_update(content)

        monkeypatch.setattr(markdown, "update", counted_update)
        action_render_version = central._action_render_version

        screen.apply_snapshot(snapshot)
        screen.apply_snapshot(snapshot)
        await pilot.pause()

        assert markdown_updates == []
        assert central._action_render_version == action_render_version


@pytest.mark.asyncio
async def test_execution_matrix_separates_owner_and_executor(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecutionMatrixScreen)
        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(
                work_package_details=[
                    WorkPackageSnapshot(
                        id="WP-001",
                        title="Rust contracts",
                        owner_agent="codex",
                        current_executor="claude",
                        last_executor="claude",
                        status="running",
                        risk="high",
                    )
                ]
            ),
        )
        await pilot.pause()

        rows = screen.query("#execution-package-list .execution-package-row")
        row_text = _widget_tree_text(rows.first())

        assert len(rows) == 1
        assert "Rust contracts" in row_text
        assert "codex" in row_text
        assert "claude fallback" in row_text
        assert "RUN" in row_text
        assert "high" in row_text
        rows.first().query_one("#wp-detail-0", Button).press()
        await pilot.pause()

        assert isinstance(app.screen, WorkPackageDetailModal)
        assert "WP-001: Rust contracts" in str(
            app.screen.query_one("#work-package-detail-title", Static).content
        )


@pytest.mark.asyncio
async def test_execution_matrix_updates_existing_rows_without_remount(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecutionMatrixScreen)
        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(
                work_package_details=[
                    WorkPackageSnapshot(
                        id="WP-001",
                        title="Runtime sync",
                        owner_agent="codex",
                        status="pending",
                    )
                ]
            ),
        )
        await pilot.pause()

        row = screen.query("#execution-package-list .execution-package-row").first()
        assert "WAIT" in _widget_tree_text(row)

        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(
                work_package_details=[
                    WorkPackageSnapshot(
                        id="WP-001",
                        title="Runtime sync",
                        owner_agent="codex",
                        current_executor="codex",
                        status="running",
                    )
                ]
            ),
        )
        await pilot.pause()

        updated_row = screen.query("#execution-package-list .execution-package-row").first()
        assert updated_row is row
        row_text = _widget_tree_text(updated_row)
        assert "RUN" in row_text
        assert "codex" in row_text


@pytest.mark.asyncio
async def test_execution_matrix_large_snapshot_updates_single_row_only(
    tmp_path,
    monkeypatch,
) -> None:
    packages = [
        WorkPackageSnapshot(
            id=f"WP-{index:03d}",
            title=f"Package {index}",
            owner_agent="codex",
            status="pending",
            parallel_group=(index % 8) + 1,
        )
        for index in range(1, 501)
    ]
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecutionMatrixScreen)
        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(work_package_details=packages),
        )
        await pilot.pause()

        rows_before = list(screen.query("#execution-package-list .execution-package-row"))
        assert len(rows_before) == 500
        original_identity = screen._package_list_identity
        update_calls: list[str] = []
        original_update = ExecutionPackageRow.update_projection

        def counted_update(
            row: ExecutionPackageRow,
            projection,
        ) -> None:
            update_calls.append(row.package_id)
            original_update(row, projection)

        monkeypatch.setattr(ExecutionPackageRow, "update_projection", counted_update)
        changed = list(packages)
        changed[249] = replace(
            packages[249],
            status="running",
            current_executor="codex",
        )
        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(work_package_details=changed),
        )
        await pilot.pause()

        rows_after = list(screen.query("#execution-package-list .execution-package-row"))
        assert len(rows_after) == 500
        assert screen._package_list_identity == original_identity
        assert rows_after[0] is rows_before[0]
        assert rows_after[249] is rows_before[249]
        assert rows_after[-1] is rows_before[-1]
        assert update_calls == ["WP-250"]
        row_text = _widget_tree_text(rows_after[249])
        assert "RUN" in row_text
        assert "codex" in row_text


@pytest.mark.asyncio
async def test_execution_matrix_skips_unchanged_chrome_updates(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-cache",
        state="executing",
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Runtime sync",
                owner_agent="codex",
                status="pending",
            )
        ],
    )

    async with app.run_test(size=(120, 36)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecutionMatrixScreen)
        screen.apply_execution_state(None, snapshot)
        await pilot.pause()

        header = screen.query_one("#execution-header", Static)
        summary = screen.query_one("#execution-summary", Static)
        updates: list[str] = []
        original_header_update = header.update
        original_summary_update = summary.update

        def counted_header_update(content) -> None:
            updates.append(f"header:{content}")
            original_header_update(content)

        def counted_summary_update(content) -> None:
            updates.append(f"summary:{content}")
            original_summary_update(content)

        header.update = counted_header_update
        summary.update = counted_summary_update

        screen.apply_execution_state(None, snapshot)
        await pilot.pause()

        assert updates == []


def test_execution_matrix_chrome_projection_scans_packages_once() -> None:
    class CountingPackages:
        def __init__(self, packages: list[WorkPackageSnapshot]) -> None:
            self.packages = packages
            self.iterations = 0

        def __iter__(self):
            self.iterations += 1
            return iter(self.packages)

        def __bool__(self) -> bool:
            return bool(self.packages)

    packages = CountingPackages(
        [
            WorkPackageSnapshot(
                id="WP-001",
                title="Running",
                owner_agent="codex",
                status="running",
                retryable=True,
                parallel_group=1,
            ),
            WorkPackageSnapshot(
                id="WP-002",
                title="Serial",
                owner_agent="claude",
                status="pending",
                parallelizable=False,
            ),
        ]
    )
    screen = ExecutionMatrixScreen()
    screen.snapshot = WorkflowNexusSnapshot(work_package_details=packages)

    projection = screen._chrome_projection()

    assert "RUN 1" in projection.summary_text
    assert "WAIT 1" in projection.summary_text
    assert "lanes 1" in projection.summary_text
    assert "serial 1" in projection.summary_text
    assert projection.retry_label == "Retry 1"
    assert projection.retry_disabled is False
    assert packages.iterations == 1


@pytest.mark.asyncio
async def test_execution_matrix_shows_parallel_group_lane(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecutionMatrixScreen)
        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(
                work_package_details=[
                    WorkPackageSnapshot(
                        id="WP-001",
                        title="Frontend shell",
                        owner_agent="codex",
                        status="running",
                        risk="medium",
                        parallel_group=1,
                    ),
                    WorkPackageSnapshot(
                        id="WP-002",
                        title="Shared config",
                        owner_agent="claude",
                        status="pending",
                        risk="high",
                        parallel_group=2,
                        parallelizable=False,
                    ),
                ],
            ),
        )
        await pilot.pause()

        header = screen.query_one(".execution-package-header")
        lane_headers = screen.query("#execution-package-list .execution-lane-header")
        rows = list(screen.query("#execution-package-list .execution-package-row"))
        summary = str(screen.query_one("#execution-summary", Static).content)

        assert "lanes 1" in summary
        assert "serial 1" in summary
        assert [str(header.render()) for header in lane_headers] == [
            "Lane g1",
            "Serial",
        ]
        assert "Risk/Lane" in _widget_tree_text(header)
        assert "risk: medium g1" in _widget_tree_text(rows[0])
        assert "risk: high serial" in _widget_tree_text(rows[1])


@pytest.mark.asyncio
async def test_execution_matrix_labels_blocked_detail_action(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecutionMatrixScreen)
        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(
                work_package_details=[
                    WorkPackageSnapshot(
                        id="WP-001",
                        title="Repair loop",
                        owner_agent="codex",
                        status="blocked",
                        repair_blocked_reason="duplicate_required_changes",
                    )
                ],
            ),
        )
        await pilot.pause()

        button = screen.query_one("#wp-detail-0", Button)
        assert str(button.label) == "Blocked"

        button.press()
        await pilot.pause()

        assert isinstance(app.screen, WorkPackageDetailModal)
        assert "duplicate_required_changes" in app.screen.render_markdown()


@pytest.mark.asyncio
async def test_execution_matrix_renders_compact_status_labels(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecutionMatrixScreen)
        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(
                work_package_details=[
                    WorkPackageSnapshot(
                        id="WP-001",
                        title="Run task",
                        owner_agent="codex",
                        status="running",
                    ),
                    WorkPackageSnapshot(
                        id="WP-002",
                        title="Wait task",
                        owner_agent="claude",
                        status="pending",
                    ),
                    WorkPackageSnapshot(
                        id="WP-002A",
                        title="User decision task",
                        owner_agent="codex",
                        status="needs_user_decision",
                    ),
                    WorkPackageSnapshot(
                        id="WP-002B",
                        title="External input task",
                        owner_agent="claude",
                        status="waiting_for_external_input",
                    ),
                    WorkPackageSnapshot(
                        id="WP-003",
                        title="Review task",
                        owner_agent="codex",
                        status="needs_review",
                    ),
                    WorkPackageSnapshot(
                        id="WP-004",
                        title="Done task",
                        owner_agent="claude",
                        status="done",
                    ),
                    WorkPackageSnapshot(
                        id="WP-004A",
                        title="Succeeded task",
                        owner_agent="codex",
                        status="succeeded",
                    ),
                    WorkPackageSnapshot(
                        id="WP-005",
                        title="Issue task",
                        owner_agent="codex",
                        status="blocked",
                    ),
                    WorkPackageSnapshot(
                        id="WP-006",
                        title="Idle task",
                        owner_agent="claude",
                        status="idle",
                    ),
                    WorkPackageSnapshot(
                        id="WP-007",
                        title="Unknown task",
                        owner_agent="codex",
                        status="paused",
                    ),
                ]
            ),
        )
        await pilot.pause()

        statuses = screen.query(
            "#execution-package-list "
            ".execution-package-row .execution-package-status"
        )

        assert [str(status.render()) for status in statuses] == [
            "RUN",
            "WAIT",
            "WAIT",
            "WAIT",
            "WAIT",
            "DONE",
            "DONE",
            "ISSUE",
            "IDLE",
            "?",
        ]


@pytest.mark.asyncio
async def test_execution_matrix_renders_korean_compact_status_labels(
    tmp_path,
) -> None:
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    )

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecutionMatrixScreen)
        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(
                work_package_details=[
                    WorkPackageSnapshot(
                        id="WP-001",
                        title="Run task",
                        owner_agent="codex",
                        status="running",
                    ),
                    WorkPackageSnapshot(
                        id="WP-002",
                        title="Wait task",
                        owner_agent="claude",
                        status="pending",
                    ),
                    WorkPackageSnapshot(
                        id="WP-003",
                        title="Done task",
                        owner_agent="claude",
                        status="done",
                    ),
                    WorkPackageSnapshot(
                        id="WP-004",
                        title="Issue task",
                        owner_agent="codex",
                        status="blocked",
                    ),
                    WorkPackageSnapshot(
                        id="WP-005",
                        title="Unknown task",
                        owner_agent="codex",
                        status="paused",
                    ),
                ]
            ),
        )
        await pilot.pause()

        statuses = screen.query(
            "#execution-package-list "
            ".execution-package-row .execution-package-status"
        )

        assert [str(status.render()) for status in statuses] == [
            "실행",
            "대기",
            "완료",
            "문제",
            "?",
        ]


@pytest.mark.asyncio
async def test_execution_matrix_summary_counts_pending_reviews(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecutionMatrixScreen)
        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(
                work_package_details=[
                    WorkPackageSnapshot(
                        id="WP-000",
                        title="Running with queued review",
                        owner_agent="codex",
                        current_executor="codex",
                        status="running",
                        review_status="queued",
                    ),
                    WorkPackageSnapshot(
                        id="WP-001",
                        title="Needs review",
                        owner_agent="codex",
                        status="needs_review",
                    ),
                    WorkPackageSnapshot(
                        id="WP-002",
                        title="Queued review",
                        owner_agent="claude",
                        status="done",
                        review_status="queued",
                    ),
                    WorkPackageSnapshot(
                        id="WP-003",
                        title="Approved",
                        owner_agent="codex",
                        status="done",
                        review_status="approved",
                    ),
                ]
            ),
        )
        await pilot.pause()

        summary = str(screen.query_one("#execution-summary", Static).content)

        assert "RUN 1" in summary
        assert "REVIEW 2" in summary
        assert "WAIT 0" in summary
        assert "DONE 1" in summary


def test_execution_matrix_compacts_reviewer_status_labels() -> None:
    assert (
        _review_label(
            WorkPackageSnapshot(
                id="WP-000",
                title="Needs review",
                owner_agent="codex",
                status="needs_review",
            )
        )
        == "queued"
    )
    assert (
        _review_label(
            WorkPackageSnapshot(
                id="WP-000K",
                title="Korean needs review",
                owner_agent="codex",
                status="needs_review",
            ),
            lang="ko",
        )
        == "대기"
    )
    assert (
        _review_label(
            WorkPackageSnapshot(
                id="WP-001",
                title="Queued by agy",
                owner_agent="codex",
                status="done",
                review_status="queued",
                reviewer_agent="antigravity",
            )
        )
        == "agy queued"
    )
    assert (
        _review_label(
            WorkPackageSnapshot(
                id="WP-002",
                title="Review by claude",
                owner_agent="codex",
                status="done",
                review_status="reviewing",
                reviewer_agent="claude",
            )
        )
        == "claude rev"
    )
    assert (
        _review_label(
            WorkPackageSnapshot(
                id="WP-003",
                title="Two reviewers",
                owner_agent="claude",
                status="done",
                review_status="reviewing",
                reviewer_agent="codex, antigravity",
            )
        )
        == "2p review"
    )
    assert (
        _review_label(
            WorkPackageSnapshot(
                id="WP-004",
                title="Three reviewers",
                owner_agent="claude",
                status="done",
                review_status="queued",
                reviewer_agent="codex, claude, antigravity",
            )
        )
        == "3p queued"
    )
    assert (
        _review_label(
            WorkPackageSnapshot(
                id="WP-005",
                title="Needs escalation",
                owner_agent="claude",
                status="done",
                review_status="needs_second_review",
                reviewer_agent="codex, antigravity",
            )
        )
        == "needs 2nd"
    )
    assert (
        _review_label(
            WorkPackageSnapshot(
                id="WP-010",
                title="No peer reviewer",
                owner_agent="codex",
                status="done",
                review_status="skipped",
                review_summary=(
                    "only codex is active; no non-owner peer reviewer is available"
                ),
            )
        )
        == "no peer"
    )
    assert (
        _review_label(
            WorkPackageSnapshot(
                id="WP-006",
                title="Korean queued review",
                owner_agent="codex",
                status="done",
                review_status="queued",
                reviewer_agent="antigravity",
            ),
            lang="ko",
        )
        == "agy 대기"
    )
    assert (
        _review_label(
            WorkPackageSnapshot(
                id="WP-007",
                title="Korean multi review",
                owner_agent="claude",
                status="done",
                review_status="reviewing",
                reviewer_agent="codex, antigravity",
            ),
            lang="ko",
        )
        == "2명 검토"
    )
    assert (
        _review_label(
            WorkPackageSnapshot(
                id="WP-008",
                title="Korean skipped review",
                owner_agent="codex",
                status="done",
                review_status="skipped",
            ),
            lang="ko",
        )
        == "생략"
    )
    assert (
        _review_label(
            WorkPackageSnapshot(
                id="WP-010",
                title="Korean no peer reviewer",
                owner_agent="codex",
                status="done",
                review_status="skipped",
                review_summary=(
                    "only codex is active; no non-owner peer reviewer is available"
                ),
            ),
            lang="ko",
        )
        == "동료 없음"
    )
    assert (
        _review_label(
            WorkPackageSnapshot(
                id="WP-009",
                title="Korean escalation",
                owner_agent="claude",
                status="done",
                review_status="needs_second_review",
                reviewer_agent="codex, antigravity",
            ),
            lang="ko",
        )
        == "2차 필요"
    )


@pytest.mark.asyncio
async def test_execution_matrix_row_labels_no_peer_review_skip(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path, lang="ko"))

    async with app.run_test(size=(120, 36)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecutionMatrixScreen)
        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(
                work_package_details=[
                    WorkPackageSnapshot(
                        id="WP-001",
                        title="Single provider package",
                        owner_agent="codex",
                        status="done",
                        review_status="skipped",
                        review_summary=(
                            "only codex is active; "
                            "no non-owner peer reviewer is available"
                        ),
                    )
                ]
            ),
        )
        await pilot.pause()

        row = screen.query("#execution-package-list .execution-package-row").first()
        row_text = _widget_tree_text(row)

        assert "리뷰: 동료 없음" in row_text


def test_execution_matrix_detail_button_labels_review_escalation() -> None:
    package = WorkPackageSnapshot(
        id="WP-001",
        title="Needs escalation",
        owner_agent="claude",
        status="done",
        review_status="needs_second_review",
    )
    blocked = WorkPackageSnapshot(
        id="WP-002",
        title="Blocked escalation",
        owner_agent="claude",
        status="blocked",
        review_status="needs_second_review",
    )
    default = WorkPackageSnapshot(
        id="WP-003",
        title="Normal",
        owner_agent="codex",
        status="done",
    )

    assert _detail_button_label(package) == "2nd Review"
    assert _detail_button_label(package, lang="ko") == "2차 리뷰"
    assert _detail_button_label(blocked) == "Blocked"
    assert _detail_button_label(blocked, lang="ko") == "차단됨"
    assert _detail_button_label(default) == "Spec"
    assert _detail_button_label(default, lang="ko") == "상세"


@pytest.mark.asyncio
async def test_execution_matrix_header_uses_two_line_row_layout(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecutionMatrixScreen)
        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(
                work_package_details=[
                    WorkPackageSnapshot(
                        id="WP-001",
                        title="프론트타입 기술 골격 수립",
                        owner_agent="codex",
                        current_executor="codex",
                        status="done",
                        review_status="-",
                        risk="high",
                    )
                ]
            ),
        )
        await pilot.pause()

        expected_primary_columns = [
            "execution-package-task",
            "execution-package-executor",
            "execution-package-status",
        ]
        expected_secondary_columns = [
            "execution-package-assignee",
            "execution-package-review",
            "execution-package-risk",
            "execution-package-actions",
        ]
        header = screen.query("#execution-package-list .execution-package-header").first()
        row = screen.query("#execution-package-list .execution-package-row").first()
        header_primary = header.query(".execution-package-primary").first()
        header_secondary = header.query(".execution-package-secondary").first()
        row_primary = row.query(".execution-package-primary").first()
        row_secondary = row.query(".execution-package-secondary").first()

        assert [
            _column_class(child, expected_primary_columns)
            for child in header_primary.children
        ] == expected_primary_columns
        assert [
            _column_class(child, expected_primary_columns)
            for child in row_primary.children
        ] == expected_primary_columns
        assert [
            _column_class(child, expected_secondary_columns)
            for child in header_secondary.children
        ] == expected_secondary_columns
        assert [
            _column_class(child, expected_secondary_columns)
            for child in row_secondary.children
        ] == expected_secondary_columns
        assert [child.region.x for child in header_primary.children] == [
            child.region.x for child in row_primary.children
        ]
        assert [child.region.x for child in header_secondary.children] == [
            child.region.x for child in row_secondary.children
        ]

        await pilot.press("f")
        await pilot.pause()

        header = screen.query("#execution-package-list .execution-package-header").first()
        row = screen.query("#execution-package-list .execution-package-row").first()
        assert [
            child.region.x
            for child in header.query(".execution-package-primary").first().children
        ] == [
            child.region.x
            for child in row.query(".execution-package-primary").first().children
        ]
        assert [
            child.region.x
            for child in header.query(".execution-package-secondary").first().children
        ] == [
            child.region.x
            for child in row.query(".execution-package-secondary").first().children
        ]


@pytest.mark.asyncio
async def test_execution_matrix_80_columns_keeps_review_risk_and_spec_visible(
    tmp_path,
) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(80, 24)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecutionMatrixScreen)
        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(
                session_id="wf-compact",
                state="executing",
                work_package_details=[
                    WorkPackageSnapshot(
                        id="WP-001",
                        title="Build compact execution dashboard rows",
                        owner_agent="codex",
                        current_executor="codex",
                        status="running",
                        review_status="queued",
                        reviewer_agent="antigravity",
                        risk="high",
                        retryable=True,
                    )
                ],
                execution_log=[f"event-{index}" for index in range(1, 12)],
                execution_recovery=ExecutionRecoverySnapshot(
                    run_id="exec-run-compact",
                    state="running",
                    retry_candidates=("WP-001",),
                ),
            ),
        )
        await pilot.pause()

        summary = str(screen.query_one("#execution-summary", Static).content)
        assert "RUN 1" in summary
        assert "retry 1" in summary
        assert "exec-run-compact" in summary

        row = screen.query("#execution-package-list .execution-package-row").first()
        row_text = _widget_tree_text(row)
        assert "review: agy queued" in row_text
        assert "risk: high" in row_text
        assert "Spec" in row_text
        for widget in row.query(
            ".execution-package-review, .execution-package-risk, .execution-package-spec"
        ):
            assert widget.region.x + widget.region.width <= 80

        activity_lines = screen.activity_lines()
        assert activity_lines[0] == "Activity"
        assert "... 4 earlier log lines hidden" in activity_lines
        assert "event-11" in activity_lines


def test_execution_matrix_recent_activity_reads_only_recent_log_window() -> None:
    class CountingLog:
        def __init__(self, lines: list[str]) -> None:
            self.lines = lines
            self.indexes: list[int] = []

        def __len__(self) -> int:
            return len(self.lines)

        def __getitem__(self, index: int) -> str:
            if isinstance(index, slice):
                raise AssertionError("recent activity should not slice the full log")
            self.indexes.append(index)
            return self.lines[index]

        def __iter__(self):
            raise AssertionError("recent activity should not iterate the full log")

    source = CountingLog([f"event-{index}" for index in range(1, 101)])
    screen = ExecutionMatrixScreen()
    screen.snapshot = WorkflowNexusSnapshot(execution_log=source)

    activity_lines = screen.activity_lines()

    assert activity_lines[0] == "Activity"
    assert "... 93 earlier log lines hidden" in activity_lines
    assert activity_lines[-1] == "event-100"
    assert source.indexes == list(range(93, 100))


@pytest.mark.asyncio
async def test_execution_matrix_row_labels_second_review_action(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 36)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecutionMatrixScreen)
        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(
                work_package_details=[
                    WorkPackageSnapshot(
                        id="WP-001",
                        title="Review escalation",
                        owner_agent="claude",
                        status="done",
                        review_status="needs_second_review",
                        reviewer_agent="codex, antigravity",
                    )
                ],
            ),
        )
        await pilot.pause()

        button = screen.query_one("#wp-detail-0", Button)
        assert str(button.label) == "2nd Review"


@pytest.mark.asyncio
async def test_execution_matrix_row_requests_second_review(tmp_path) -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-second-review",
        goal="review escalation",
        state="reviewing",
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Review escalation",
                owner_agent="claude",
                status="done",
                review_status="needs_second_review",
                reviewer_agent="codex, antigravity",
            ),
            WorkPackageSnapshot(
                id="WP-002",
                title="Normal package",
                owner_agent="codex",
                status="done",
                review_status="approved",
                reviewer_agent="antigravity",
            ),
        ],
    )
    controller = FakeWorkflowController(snapshot)
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecutionMatrixScreen)
        screen.apply_execution_state(None, snapshot)
        await pilot.pause()

        review_button = screen.query_one("#wp-review-0", Button)
        assert str(review_button.label) == "Run 2nd"
        assert review_button.region.x + review_button.region.width <= 100
        detail_button = screen.query_one("#wp-detail-0", Button)
        assert detail_button.region.x + detail_button.region.width <= 100
        assert not screen.query("#wp-review-1")

        review_button.press()
        await pilot.pause()

        assert controller.review_requests == [("wp", "WP-001")]


@pytest.mark.asyncio
async def test_execution_matrix_viewport_qa_matrix_with_long_workspace(
    tmp_path,
) -> None:
    target = (
        tmp_path
        / "workspace"
        / "very-long-project-name-for-terminal-qa"
        / "nested-package"
    )
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-viewport-qa",
        state="executing",
        target_workspace=str(target),
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Parallel implementation lane with a deliberately long title",
                owner_agent="codex",
                current_executor="codex",
                status="running",
                review_status="queued",
                reviewer_agent="antigravity",
                risk="medium",
                parallel_group=1,
            ),
            WorkPackageSnapshot(
                id="WP-002",
                title="Blocked repair follow-up lane",
                owner_agent="claude",
                status="blocked",
                risk="high",
                parallel_group=2,
                parallelizable=False,
                retryable=True,
                repair_blocked_reason="duplicate_required_changes",
            ),
        ],
        execution_log=[f"event-{index}" for index in range(1, 14)],
        execution_recovery=ExecutionRecoverySnapshot(
            run_id="exec-run-viewport-qa",
            state="running",
            retry_candidates=("WP-002",),
            target_workspace=str(target),
        ),
    )

    for width, height in ((80, 24), (100, 30), (120, 40)):
        config = TrinityConfig.default_config(project_dir=tmp_path)
        config.lang = "ko"
        app = TrinityTextualApp(config)

        async with app.run_test(size=(width, height)) as pilot:
            app.switch_to("execution")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ExecutionMatrixScreen)
            screen.apply_execution_state(None, snapshot)
            await pilot.pause()

            summary = str(screen.query_one("#execution-summary", Static).content)
            assert "실행 중 1" in summary
            assert "리뷰 0" in summary
            assert "대기 0" in summary
            assert "완료 0" in summary
            assert "문제 1" in summary
            assert "그룹 1" in summary
            assert "직렬 1" in summary
            assert "재시도 1" in summary
            assert "워크플로우 실행 중" in summary
            assert "실행 exec-run-viewport-qa" in summary
            assert "대상:" in summary

            for selector in (
                "#toggle-task-expanded",
                "#toggle-activity-expanded",
                "#execution-retry",
            ):
                widget = screen.query_one(selector, Button)
                assert widget.region.x + widget.region.width <= width

            rows = list(screen.query("#execution-package-list .execution-package-row"))
            assert len(rows) == 2
            assert "리뷰: agy 대기" in _widget_tree_text(rows[0])
            assert "리스크: 보통 g1" in _widget_tree_text(rows[0])
            assert "리스크: 높음 직렬" in _widget_tree_text(rows[1])

            blocked_button = screen.query_one("#wp-detail-1", Button)
            assert str(blocked_button.label) == "차단됨"
            assert blocked_button.region.x + blocked_button.region.width <= width

            for row in rows:
                for widget in row.query(
                    ".execution-package-review, "
                    ".execution-package-risk, "
                    ".execution-package-spec"
                ):
                    assert widget.region.x + widget.region.width <= width

            activity_lines = screen.activity_lines()
            assert activity_lines[0] == "활동"
            assert len(activity_lines) <= 9
            assert "event-13" in activity_lines


@pytest.mark.asyncio
async def test_execution_matrix_surfaces_skipped_review_reason(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(100, 30)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecutionMatrixScreen)
        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(
                work_package_details=[
                    WorkPackageSnapshot(
                        id="WP-001",
                        title="Single provider package",
                        owner_agent="codex",
                        status="done",
                        review_status="skipped",
                        review_summary=(
                            "only codex is active; no non-owner peer reviewer is available"
                        ),
                    )
                ],
            ),
        )
        await pilot.pause()

        row = screen.query("#execution-package-list .execution-package-row").first()
        assert "review: no peer" in _widget_tree_text(row)
        row.query_one("#wp-detail-0", Button).press()
        await pilot.pause()

        assert isinstance(app.screen, WorkPackageDetailModal)
        markdown = app.screen.render_markdown()
        assert "- Status: `skipped`" in markdown
        assert (
            "- Review skipped reason: only codex is active; "
            "no non-owner peer reviewer is available"
        ) in markdown
        assert "no non-owner peer reviewer is available" in markdown


@pytest.mark.asyncio
async def test_execution_matrix_opens_full_activity_log_modal(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 36)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecutionMatrixScreen)
        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(
                execution_log=[f"event-{index}" for index in range(1, 12)],
            ),
        )
        await pilot.pause()

        assert "Full Log" in str(
            screen.query_one("#toggle-activity-expanded", Button).label
        )
        recent_lines = screen.activity_lines()
        assert "... 4 earlier log lines hidden" in recent_lines
        assert "event-1" not in recent_lines

        screen.query_one("#toggle-activity-expanded", Button).press()
        await pilot.pause()

        assert isinstance(app.screen, ExecutionLogModal)
        assert app.screen.lines[0] == "event-1"
        assert app.screen.lines[-1] == "event-11"
        assert str(app.screen.query_one("#execution-log-modal-title", Static).content) == (
            "Full Execution Log"
        )
        assert screen.activity_lines() == recent_lines


@pytest.mark.asyncio
async def test_execution_matrix_supports_korean_chrome_labels(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    app = TrinityTextualApp(config)

    async with app.run_test(size=(120, 36)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecutionMatrixScreen)

        assert _binding_description(
            screen._bindings, "f", "toggle_task_expanded"
        ) == "작업 펼치기"
        assert str(screen.query_one("#execution-header", Static).content).startswith(
            "실행 매트릭스"
        )
        assert "작업 폴더: 선택 안 됨" in str(
            screen.query_one("#execution-header", Static).content
        )
        assert str(screen.query_one("#toggle-task-expanded", Button).label) == (
            "작업 펼치기"
        )
        assert str(screen.query_one("#toggle-activity-expanded", Button).label) == (
            "전체 로그"
        )
        screen.apply_execution_state(None, WorkflowNexusSnapshot())
        await pilot.pause()
        empty_text = str(
            screen.query("#execution-package-list .execution-package-empty")
            .first()
            .render()
        )
        assert "(작업 패키지 없음)" in empty_text

        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(
                execution_log=[f"event-{index}" for index in range(1, 10)],
                work_package_details=[
                    WorkPackageSnapshot(
                        id="WP-001",
                        title="Client",
                        owner_agent="codex",
                        current_executor="claude",
                        status="failed",
                        retryable=True,
                        review_status="queued",
                        reviewer_agent="antigravity",
                        risk="medium",
                    ),
                    WorkPackageSnapshot(
                        id="WP-002",
                        title="Docs",
                        owner_agent="claude",
                        status="pending",
                        risk="",
                    ),
                ],
                execution_recovery=ExecutionRecoverySnapshot(
                    state="failed",
                    retry_candidates=("WP-001",),
                ),
            ),
        )
        await pilot.pause()

        assert str(screen.query_one("#execution-retry", Button).label) == "재시도 1"
        header_text = _widget_tree_text(
            screen.query("#execution-package-list .execution-package-header").first()
        )
        assert "패키지 / 작업" in header_text
        assert "실행자" in header_text
        assert "리스크/그룹" in header_text

        rows = list(screen.query("#execution-package-list .execution-package-row"))
        first_row_text = _widget_tree_text(rows[0])
        second_row_text = _widget_tree_text(rows[1])
        assert "claude 대체" in first_row_text
        assert "리뷰: agy 대기" in first_row_text
        assert "리스크: 보통" in first_row_text
        assert "상세" in first_row_text
        assert "리스크: 알 수 없음" in second_row_text

        activity_lines = screen.activity_lines()
        assert activity_lines[0] == "활동"
        assert "... 이전 로그 2줄 숨김" in activity_lines

        screen.query_one("#toggle-activity-expanded", Button).press()
        await pilot.pause()

        assert isinstance(app.screen, ExecutionLogModal)
        assert str(app.screen.query_one("#execution-log-modal-title", Static).content) == (
            "전체 실행 로그"
        )


def test_execution_log_modal_keeps_short_logs_complete() -> None:
    lines = [f"event-{index}" for index in range(1, MAX_RENDERED_LOG_LINES + 1)]
    modal = ExecutionLogModal(lines)

    assert modal.render_log_lines() == lines


def test_execution_log_modal_windows_large_logs() -> None:
    lines = [f"event-{index}" for index in range(1, MAX_RENDERED_LOG_LINES + 26)]
    modal = ExecutionLogModal(lines)
    rendered = modal.render_log_lines()

    assert rendered[0] == "... 25 earlier log lines hidden"
    assert rendered[1] == "event-26"
    assert rendered[-1] == f"event-{MAX_RENDERED_LOG_LINES + 25}"
    assert "event-1" not in rendered
    assert len(rendered) == MAX_RENDERED_LOG_LINES + 1


def test_execution_log_modal_unfiltered_window_avoids_full_iteration() -> None:
    class CountingLog:
        def __init__(self, lines: list[str]) -> None:
            self.lines = lines
            self.indexes: list[int] = []

        def __len__(self) -> int:
            return len(self.lines)

        def __getitem__(self, index: int) -> str:
            if isinstance(index, slice):
                raise AssertionError("unfiltered log window should not slice all lines")
            self.indexes.append(index)
            return self.lines[index]

        def __iter__(self):
            raise AssertionError("unfiltered log window should not iterate all lines")

    source = CountingLog(
        [f"event-{index}" for index in range(1, MAX_RENDERED_LOG_LINES + 26)]
    )
    modal = ExecutionLogModal([])
    modal.lines = source

    assert modal.status_text() == (
        f"Showing {MAX_RENDERED_LOG_LINES} of {MAX_RENDERED_LOG_LINES + 25} lines"
    )

    rendered = modal.render_log_lines()

    assert rendered[0] == "... 25 earlier log lines hidden"
    assert rendered[1] == "event-26"
    assert rendered[-1] == f"event-{MAX_RENDERED_LOG_LINES + 25}"
    assert source.indexes == list(range(25, MAX_RENDERED_LOG_LINES + 25))


def test_execution_log_modal_reports_visible_line_count() -> None:
    short = ExecutionLogModal(["event-1", "event-2"])
    large = ExecutionLogModal(
        [f"event-{index}" for index in range(1, MAX_RENDERED_LOG_LINES + 26)]
    )
    korean = ExecutionLogModal(["event-1", "event-2"], lang="ko")

    assert short.status_text() == "Showing 2 of 2 lines"
    assert large.status_text() == (
        f"Showing {MAX_RENDERED_LOG_LINES} of {MAX_RENDERED_LOG_LINES + 25} lines"
    )
    assert korean.status_text() == "2/2줄 표시"


def test_execution_log_modal_filters_lines_case_insensitively() -> None:
    modal = ExecutionLogModal(
        [
            "WP-001 started by codex",
            "WP-002 failed with provider error",
            "WP-003 review completed",
            "wp-004 FAILED after retry",
        ]
    )

    assert modal.render_log_lines("FAILED") == [
        "WP-002 failed with provider error",
        "wp-004 FAILED after retry",
    ]
    assert modal.render_log_lines("review") == ["WP-003 review completed"]
    assert modal.status_text("FAILED") == "Showing 2 of 2 matches"


def test_execution_log_modal_render_state_filters_once() -> None:
    class CountingExecutionLogModal(ExecutionLogModal):
        def __init__(self, lines: list[str]) -> None:
            super().__init__(lines)
            self.filter_calls = 0

        def _filtered_lines(self, query: str) -> list[str]:
            self.filter_calls += 1
            return super()._filtered_lines(query)

    modal = CountingExecutionLogModal(
        [
            "WP-001 started by codex",
            "WP-002 failed with provider error",
            "WP-003 review completed",
            "wp-004 FAILED after retry",
        ]
    )

    status, rendered = modal._render_state("FAILED")

    assert status == "Showing 2 of 2 matches"
    assert rendered == [
        "WP-002 failed with provider error",
        "wp-004 FAILED after retry",
    ]
    assert modal.filter_calls == 1


def test_execution_log_modal_filters_large_match_sets() -> None:
    lines = [f"WP-{index:03d} failed" for index in range(1, MAX_RENDERED_LOG_LINES + 4)]
    modal = ExecutionLogModal(lines)
    rendered = modal.render_log_lines("failed")

    assert rendered[0] == "... 3 earlier log lines hidden"
    assert rendered[1] == "WP-004 failed"
    assert rendered[-1] == f"WP-{MAX_RENDERED_LOG_LINES + 3:03d} failed"
    assert modal.status_text("failed") == (
        f"Showing {MAX_RENDERED_LOG_LINES} of {MAX_RENDERED_LOG_LINES + 3} matches"
    )


def test_execution_log_modal_shows_empty_filtered_state() -> None:
    modal = ExecutionLogModal(["WP-001 started"])
    korean = ExecutionLogModal(["WP-001 started"], lang="ko")

    assert modal.render_log_lines("missing") == ["No matching execution log lines."]
    assert korean.render_log_lines("missing") == ["일치하는 실행 로그가 없습니다."]
    assert modal.status_text("missing") == "0 matches"
    assert korean.status_text("missing") == "0개 결과"


def test_execution_log_modal_localizes_large_log_window() -> None:
    lines = [f"event-{index}" for index in range(1, MAX_RENDERED_LOG_LINES + 3)]
    modal = ExecutionLogModal(lines, lang="ko")

    assert modal.render_log_lines()[0] == "... 이전 로그 2줄 숨김"


def test_execution_log_modal_keeps_empty_state() -> None:
    assert ExecutionLogModal([]).render_log_lines() == ["No execution log yet."]
    assert ExecutionLogModal([], lang="ko").render_log_lines() == [
        "실행 로그가 아직 없습니다."
    ]


@pytest.mark.asyncio
async def test_execution_log_modal_search_input_refreshes_log(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 36)) as pilot:
        app.push_screen(
            ExecutionLogModal(
                [
                    "WP-001 started",
                    "WP-002 failed with provider error",
                    "WP-003 completed",
                ]
            )
        )
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, ExecutionLogModal)
        await pilot.click("#execution-log-search")
        await pilot.press("f", "a", "i", "l")
        await pilot.pause()

        output = modal.query_one("#execution-log-modal-body", RichLog)
        status = modal.query_one("#execution-log-search-status", Static)
        text = "\n".join(line.text for line in output.lines)
        assert modal.filter_query == "fail"
        assert str(status.content) == "Showing 1 of 1 matches"
        assert "WP-002 failed with provider error" in text
        assert "WP-001 started" not in text


def test_work_package_detail_modal_orders_execution_sections_first() -> None:
    modal = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-001",
            title="Dashboard",
            owner_agent="codex",
            status="done",
            objective="Improve execution UI",
            review_status="approved",
            last_result_status="succeeded",
            last_result_summary="Rows fit compact terminals.",
            task_kind="implementation",
            routing_reason="implementation strength 0.95",
            routing_score=111.0,
            profile_revision="default-v1",
            parallel_group=1,
        )
    )
    markdown = modal.render_markdown()

    assert markdown.index("## Summary") < markdown.index("## Result")
    assert markdown.index("## Action Context") < markdown.index("## Result")
    assert markdown.index("## Result") < markdown.index("## Review Plan")
    assert markdown.index("## Review Plan") < markdown.index("\n## Review\n")
    assert markdown.index("\n## Review\n") < markdown.index("## Spec")
    assert "- Execution lane: `g1`" in markdown
    assert "Routing reason: implementation strength 0.95" in markdown
    assert "- Reviewer count: `0`" in markdown


def test_work_package_detail_modal_surfaces_retry_action_context() -> None:
    modal = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-001",
            title="Client",
            owner_agent="codex",
            status="failed",
            retryable=True,
            last_result_status="failed",
            last_result_summary="Could not finish.",
            last_result_blockers=["Missing schema.", "Tests failed."],
            review_status="changes_requested",
            review_required_changes=["Add retry regression coverage."],
        )
    )

    markdown = modal.render_markdown()

    assert "## Action Context" in markdown
    assert "- Retry candidate: `WP-001`" in markdown
    assert "- Blocking evidence: Missing schema." in markdown
    assert "- Additional blockers: 1" in markdown
    assert "- Review requested 1 change before completion." in markdown


def test_work_package_detail_modal_surfaces_retry_disabled_reason() -> None:
    modal = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-002",
            title="Docs",
            owner_agent="claude",
            status="done",
            retryable=False,
            retry_disabled_reason="already done",
        )
    )

    markdown = modal.render_markdown()

    assert "- Retry unavailable: already done" in markdown
    assert "- Retry candidate: `WP-002`" not in markdown


def test_work_package_detail_modal_localizes_korean_retry_disabled_reason() -> None:
    modal = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-002",
            title="문서",
            owner_agent="claude",
            status="done",
            retryable=False,
            retry_disabled_reason="already done",
        ),
        lang="ko",
    )

    markdown = modal.render_markdown()

    assert "- 재시도 불가: 이미 완료됨" in markdown
    assert "- 재시도 후보: `WP-002`" not in markdown
    assert "already done" not in markdown


def test_work_package_detail_modal_localizes_korean_retry_disabled_reason_variants() -> None:
    modal = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-002",
            title="문서",
            owner_agent="claude",
            status="needs_review",
            retryable=False,
            retry_disabled_reason="already needs review",
        ),
        lang="ko",
    )
    no_execution_modal = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-003",
            title="문서",
            owner_agent="codex",
            status="pending",
            retryable=False,
            retry_disabled_reason="does not require execution",
        ),
        lang="ko",
    )
    pending_modal = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-004",
            title="문서",
            owner_agent="antigravity",
            status="pending",
            retryable=False,
            retry_disabled_reason="status is pending",
        ),
        lang="ko",
    )
    custom_modal = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-005",
            title="문서",
            owner_agent="codex",
            status="pending",
            retryable=False,
            retry_disabled_reason="custom policy",
        ),
        lang="ko",
    )

    assert "- 재시도 불가: 이미 리뷰 대기 중" in modal.render_markdown()
    assert "- 재시도 불가: 실행이 필요하지 않음" in no_execution_modal.render_markdown()
    assert "- 재시도 불가: 현재 상태가 대기 상태임" in pending_modal.render_markdown()
    assert "- 재시도 불가: custom policy" in custom_modal.render_markdown()


def test_work_package_detail_modal_surfaces_review_skip_reason() -> None:
    modal = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-003",
            title="Single provider",
            owner_agent="codex",
            status="done",
            review_status="skipped",
            review_summary=(
                "only codex is active; no non-owner peer reviewer is available"
            ),
        )
    )

    markdown = modal.render_markdown()

    assert (
        "- Review skipped reason: only codex is active; "
        "no non-owner peer reviewer is available"
    ) in markdown
    assert "## Review Plan" in markdown
    assert "- Reviewer count: `0`" in markdown
    assert "Peer review was skipped; treat confidence as lower." not in markdown


def test_work_package_detail_modal_keeps_review_skip_fallback() -> None:
    modal = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-004",
            title="Legacy skipped review",
            owner_agent="codex",
            status="done",
            review_status="skipped",
        )
    )

    markdown = modal.render_markdown()

    assert "- Peer review was skipped; treat confidence as lower." in markdown


def test_work_package_detail_modal_keeps_korean_review_skip_fallback() -> None:
    modal = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-004",
            title="레거시 생략 리뷰",
            owner_agent="codex",
            status="done",
            review_status="skipped",
        ),
        lang="ko",
    )

    markdown = modal.render_markdown()

    assert "- 동료 리뷰가 생략되었습니다. 신뢰도를 낮게 보세요." in markdown
    assert "Peer review가 생략되었습니다" not in markdown


def test_work_package_detail_modal_surfaces_korean_review_skip_reason() -> None:
    modal = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-005",
            title="단일 provider",
            owner_agent="codex",
            status="done",
            review_status="skipped",
            review_summary=(
                "only codex is active; no non-owner peer reviewer is available"
            ),
        ),
        lang="ko",
    )

    markdown = modal.render_markdown()

    assert (
        "- 리뷰 생략 사유: 활성 에이전트가 codex뿐이라 "
        "동료 리뷰어가 없습니다."
    ) in markdown
    assert "## 리뷰 계획" in markdown


def test_work_package_detail_modal_localizes_korean_generic_review_skip_summary() -> None:
    modal = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-005",
            title="일반 생략 리뷰",
            owner_agent="codex",
            status="done",
            review_status="skipped",
            review_summary="Peer review skipped.",
        ),
        lang="ko",
    )

    markdown = modal.render_markdown()

    assert "- 리뷰 생략 사유: 동료 리뷰가 생략되었습니다." in markdown
    assert "Peer review skipped" not in markdown


def test_work_package_detail_modal_surfaces_second_review_plan() -> None:
    modal = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-006",
            title="Needs second review",
            owner_agent="claude",
            status="done",
            review_status="needs_second_review",
            reviewer_agent="codex, antigravity",
            review_summary="Primary review requested changes.",
        )
    )

    markdown = modal.render_markdown()

    assert "## Review Plan" in markdown
    assert "- Status: `needs_second_review`" in markdown
    assert "- Reviewer: `codex, antigravity`" in markdown
    assert "- Reviewer count: `2`" in markdown
    assert "- Second review is pending." in markdown


def test_work_package_detail_modal_localizes_korean_status_values() -> None:
    modal = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-011",
            title="상태 표시",
            owner_agent="codex",
            status="failed",
            last_result_status="failed",
            last_result_summary="Could not finish.",
            review_status="changes_requested",
            review_required_changes=["Add retry regression coverage."],
            acceptance_criteria=["재시도 흐름이 문서화된다."],
            repair_attempt_count=2,
            repair_max_attempts=3,
            repair_blocked_reason="duplicate_required_changes",
            repair_notes=["필수 변경이 반복됨"],
        ),
        lang="ko",
    )

    markdown = modal.render_markdown()

    assert "- 상태: `실패`" in markdown
    assert "- 리뷰: `변경 요청`" in markdown
    assert "- 보정 시도: `2/3`" in markdown
    assert "- 차단 사유: `duplicate_required_changes`" in markdown
    assert "- 보정 루프가 `2/3` 시도 후 차단됨: duplicate_required_changes" in markdown
    assert "## 리뷰 계획\n- 상태: `변경 요청`" in markdown
    assert "## 리뷰\n- 리뷰어: `-`\n- 상태: `변경 요청`" in markdown
    assert "## 인수 기준\n- 재시도 흐름이 문서화된다." in markdown
    assert "## 보정 메모\n- 필수 변경이 반복됨" in markdown
    assert "- 리뷰가 완료 전 1개 변경을 요청했습니다." in markdown
    assert "`changes_requested`" not in markdown


def test_work_package_detail_modal_localizes_korean_risk_and_severity_values() -> None:
    modal = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-013",
            title="리스크 표시",
            owner_agent="codex",
            status="done",
            risk="high",
            review_status="changes_requested",
            review_severity="medium",
            review_summary="보통 심각도 리뷰",
        ),
        lang="ko",
    )

    markdown = modal.render_markdown()

    assert "- 리스크: `높음`" in markdown
    assert "- 심각도: `보통`" in markdown
    assert "`high`" not in markdown
    assert "`medium`" not in markdown


def test_work_package_detail_modal_localizes_korean_task_kind_value() -> None:
    modal = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-015",
            title="작업 유형 표시",
            owner_agent="codex",
            status="pending",
            task_kind="implementation",
            routing_reason="implementation strength",
            profile_revision="default-v1",
        ),
        lang="ko",
    )

    markdown = modal.render_markdown()

    assert "- 작업 유형: `구현`" in markdown
    assert "- 라우팅 사유: 구현 강점" in markdown
    assert "- 프로필 버전: `default-v1`" in markdown
    assert "`implementation`" not in markdown


def test_work_package_detail_modal_localizes_empty_risk_placeholder() -> None:
    korean = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-014",
            title="리스크 표시",
            owner_agent="codex",
            status="pending",
            risk="",
        ),
        lang="ko",
    )
    english = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-014",
            title="Risk display",
            owner_agent="codex",
            status="pending",
            risk="",
        ),
        lang="en",
    )

    assert "- 리스크: `알 수 없음`" in korean.render_markdown()
    assert "- Risk: `unknown`" in english.render_markdown()


def test_work_package_detail_modal_localizes_korean_second_review_status() -> None:
    modal = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-012",
            title="2차 리뷰",
            owner_agent="claude",
            status="done",
            review_status="needs_second_review",
            reviewer_agent="codex, antigravity",
            review_summary="Primary review requested changes.",
        ),
        lang="ko",
    )

    markdown = modal.render_markdown()

    assert "- 상태: `완료`" in markdown
    assert "- 리뷰: `2차 리뷰 필요`" in markdown
    assert "## 리뷰 계획\n- 상태: `2차 리뷰 필요`" in markdown
    assert "- 2차 리뷰가 대기 중입니다." in markdown
    assert "`needs_second_review`" not in markdown


def test_work_package_detail_modal_localizes_known_external_input_status() -> None:
    modal = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-013",
            title="Unknown status",
            owner_agent="codex",
            status="waiting_for_external_input",
        ),
        lang="ko",
    )

    markdown = modal.render_markdown()

    assert "- 상태: `외부 입력 대기`" in markdown
    assert "waiting_for_external_input" not in markdown


@pytest.mark.asyncio
async def test_work_package_detail_modal_supports_korean_chrome_labels(
    tmp_path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    app = TrinityTextualApp(config)

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecutionMatrixScreen)
        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(
                work_package_details=[
                    WorkPackageSnapshot(
                        id="WP-001",
                        title="Client",
                        owner_agent="codex",
                        status="failed",
                        retryable=True,
                        last_result_status="failed",
                        last_result_summary="Could not finish.",
                        last_result_blockers=["Missing schema."],
                        review_status="changes_requested",
                        review_required_changes=["Add retry regression coverage."],
                    )
                ],
            ),
        )
        await pilot.pause()

        screen.query_one("#wp-detail-0", Button).press()
        await pilot.pause()

        assert isinstance(app.screen, WorkPackageDetailModal)
        assert str(app.screen.query_one("#close-work-package-detail", Button).label) == (
            "닫기"
        )
        markdown = app.screen.render_markdown()
        assert "## 요약" in markdown
        assert "- 제목: Client" in markdown
        assert "- 상태: `실패`" in markdown
        assert "- 리뷰: `변경 요청`" in markdown
        assert "- 소유자: `codex`" in markdown
        assert "- 실행 필요: `예`" in markdown
        assert "## 작업 맥락" in markdown
        assert "- 재시도 후보: `WP-001`" in markdown
        assert "- 차단 근거: Missing schema." in markdown
        assert "- 리뷰가 완료 전 1개 변경을 요청했습니다." in markdown
        assert "## 결과" in markdown
        assert "## 리뷰" in markdown
        assert "## 명세" in markdown
        assert "### 목표" in markdown


def test_work_package_detail_modal_clips_header_and_preserves_full_title() -> None:
    long_title = "Build " + "very long package title " * 8
    modal = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-999",
            title=long_title,
            topic="Execution detail topic",
            owner_agent="codex",
            status="pending",
        )
    )

    title_text = modal.title_text()
    markdown = modal.render_markdown()

    assert len(title_text) <= 86
    assert title_text.endswith("...")
    assert f"- Title: {long_title}" in markdown
    assert "- Topic: Execution detail topic" in markdown


def test_work_package_detail_modal_marks_serial_execution_lane() -> None:
    modal = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-001",
            title="Shared config",
            owner_agent="claude",
            status="pending",
            parallel_group=2,
            parallelizable=False,
        )
    )

    assert "- Execution lane: `serial`" in modal.render_markdown()


def test_work_package_detail_modal_localizes_korean_execution_lane() -> None:
    serial = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-008",
            title="직렬 작업",
            owner_agent="codex",
            status="pending",
            parallelizable=False,
        ),
        lang="ko",
    )
    unspecified = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-009",
            title="미지정 작업",
            owner_agent="codex",
            status="pending",
            parallelizable=True,
        ),
        lang="ko",
    )
    grouped = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-010",
            title="그룹 작업",
            owner_agent="codex",
            status="pending",
            parallel_group=3,
        ),
        lang="ko",
    )

    assert "- 실행 그룹: `직렬`" in serial.render_markdown()
    assert "- 실행 그룹: `미지정`" in unspecified.render_markdown()
    assert "- 실행 그룹: `g3`" in grouped.render_markdown()


def test_provider_inspector_meta_includes_profile_summary() -> None:
    inspector = ProviderInspector(
        [
            ProviderSnapshot(
                name="codex",
                provider="codex",
                enabled=True,
                status="Ready",
                readiness="ready",
                profile_mission="Implementation and testing",
                profile_modes=["execute", "review"],
                profile_strengths=["implementation 0.95"],
                context_profile="implementer",
                output_contract="execution_v1",
                quality_signal_count=3,
                quality_success_count=2,
                quality_blocker_count=1,
                quality_required_change_count=4,
                quality_score=0.667,
            )
        ]
    )

    meta = inspector._provider_meta(inspector.providers[0])

    assert "Mission: Implementation and testing" in meta
    assert "Modes: execute, review" in meta
    assert "Strengths: implementation 0.95" in meta
    assert "Context profile: implementer" in meta
    assert "Output contract: execution_v1" in meta
    assert "Quality signals: score 0.667, success 2/3" in meta
    assert "blockers 1, required changes 4" in meta


def test_provider_inspector_meta_uses_korean_labels() -> None:
    inspector = ProviderInspector(
        [
            ProviderSnapshot(
                name="codex",
                provider="codex",
                enabled=True,
                status="Ready",
                readiness="ready",
                profile_mission="Implementation and testing",
                profile_modes=["execute", "review"],
                profile_strengths=["implementation 0.95"],
                context_profile="implementer",
                output_contract="execution_v1",
                quality_signal_count=3,
                quality_success_count=2,
                quality_blocker_count=1,
                quality_required_change_count=4,
                quality_score=0.667,
            )
        ],
        lang="ko",
    )

    meta = inspector._provider_meta(inspector.providers[0])
    all_output = inspector._all_output()

    assert "프로바이더: codex" in meta
    assert "상태: 준비됨" in meta
    assert "준비 상태: 준비됨" in meta
    assert "미션: Implementation and testing" in meta
    assert "모드: 실행, 리뷰" in meta
    assert "강점: 구현 0.95" in meta
    assert "컨텍스트 프로필: 구현자" in meta
    assert "출력 형식: 실행 v1" in meta
    assert "품질 신호: 점수 0.667, 성공 2/3" in meta
    assert "차단 1, 변경 요청 4" in meta
    assert "품질 신호: 점수 0.667, 성공 2/3" in all_output


@pytest.mark.asyncio
async def test_execution_matrix_expands_task_area(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))
    long_title = (
        "Build a very long execution task title with detailed Korean and English "
        "context for monitoring"
    )

    async with app.run_test(size=(150, 44)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecutionMatrixScreen)
        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(
                work_package_details=[
                    WorkPackageSnapshot(
                        id="WP-001",
                        title=long_title,
                        owner_agent="codex",
                        status="pending",
                    )
                ]
            ),
        )
        await pilot.pause()

        compact_row = screen.query("#execution-package-list .execution-package-row").first()
        compact_text = _widget_tree_text(compact_row)
        execution_screen = screen.query_one("#execution-screen")
        assert not execution_screen.has_class("execution-task-expanded")
        assert "detailed Korean" not in compact_text

        await pilot.press("f")
        await pilot.pause()

        expanded_row = screen.query("#execution-package-list .execution-package-row").first()
        expanded_text = _widget_tree_text(expanded_row)
        assert screen.tasks_expanded is True
        assert execution_screen.has_class("execution-task-expanded")
        assert "detailed Korean" in expanded_text
        assert str(screen.query_one("#toggle-task-expanded", Button).label) == "Compact Tasks"

        screen.query_one("#toggle-task-expanded", Button).press()
        await pilot.pause()

        assert screen.tasks_expanded is False
        assert not execution_screen.has_class("execution-task-expanded")
        assert str(screen.query_one("#toggle-task-expanded", Button).label) == "Expand Tasks"


@pytest.mark.asyncio
async def test_provider_panel_shows_summary_and_keeps_raw_in_inspector(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))
    long_output = "\n".join(f"line {index}" for index in range(30))

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)
        screen.apply_snapshot(
            WorkflowNexusSnapshot(
                providers=[
                    ProviderSnapshot(
                        name="claude",
                        provider="claude-code",
                        enabled=True,
                        status="Ready",
                        summary="short summary",
                        raw_output=long_output,
                    )
                ]
            )
        )
        await pilot.pause()

        panel = screen.query_one("#provider-claude", ProviderPanel)
        assert "short summary" in str(panel.query_one(".provider-summary").content)
        assert "line 29" not in str(panel.query_one(".provider-summary").content)
        assert panel.has_class("provider-state-done")

        screen.action_open_inspector()
        await pilot.pause()

        assert isinstance(app.screen, ProviderInspector)
        assert "line 29" in provider_inspector_provider_output(
            app.screen.providers[0],
            lang=app.screen.lang,
        )


@pytest.mark.asyncio
async def test_workflow_inspector_renders_snapshot_counts(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(140, 42)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)
        screen.apply_snapshot(
            WorkflowNexusSnapshot(
                session_id="wf-inspector",
                state="blueprint_ready",
                round_num=1,
                decisions=["Use Textual"],
                work_packages=["WP-001 codex: UI shell (pending)"],
                work_package_details=[
                    WorkPackageSnapshot(
                        id="WP-001",
                        title="UI shell",
                        owner_agent="codex",
                        status="done",
                    ),
                    WorkPackageSnapshot(
                        id="WP-002",
                        title="Renderer",
                        owner_agent="claude",
                        status="running",
                        current_executor="claude",
                    ),
                    WorkPackageSnapshot(
                        id="WP-003",
                        title="Validation",
                        owner_agent="antigravity",
                        status="pending",
                        dependencies=["WP-002"],
                    ),
                    WorkPackageSnapshot(
                        id="WP-004",
                        title="Adapter",
                        owner_agent="codex",
                        status="blocked",
                        repair_blocked_reason="missing token",
                        repair_attempt_count=2,
                        repair_max_attempts=2,
                    ),
                    WorkPackageSnapshot(
                        id="WP-005",
                        title="Docs",
                        owner_agent="codex",
                        status="pending",
                        dependencies=["WP-001"],
                        parallel_group=2,
                    ),
                ],
                execution_log=["state_changed: blueprint_ready"],
            )
        )
        await pilot.pause()

        inspector = screen.query_one(WorkflowInspector)
        assert "wf-inspector" in str(inspector.query_one("#inspector-workflow").content)
        assert "Use Textual" in str(inspector.query_one("#inspector-decisions").content)
        assert "5 WP · 1 done · 1 running · 2 waiting · 1 blocked" in str(
            inspector.query_one("#inspector-progress").content
        )
        assert "[#>..!]" in str(inspector.query_one("#inspector-progress").content)
        assert "WP-002 Claude · Renderer" in str(
            inspector.query_one("#inspector-current").content
        )
        next_content = str(inspector.query_one("#inspector-next").content)
        assert "WP-005 Codex · Docs · group 2" in next_content
        assert "WP-003 Antigravity · Validation" in next_content
        assert "waiting on WP-002" in next_content
        assert next_content.index("WP-005") < next_content.index("WP-003")
        assert "WP-004 Codex · Adapter" in str(
            inspector.query_one("#inspector-blocked").content
        )
        assert "repair 2/2 · missing token" in str(
            inspector.query_one("#inspector-blocked").content
        )


@pytest.mark.asyncio
async def test_workflow_inspector_uses_configured_korean_labels(tmp_path) -> None:
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    )

    async with app.run_test(size=(140, 42)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)
        screen.apply_snapshot(
            WorkflowNexusSnapshot(
                session_id="wf-inspector-ko",
                state="blueprint_ready",
                round_num=1,
                work_package_details=[
                    WorkPackageSnapshot(
                        id="WP-001",
                        title="UI shell",
                        owner_agent="codex",
                        status="done",
                    ),
                    WorkPackageSnapshot(
                        id="WP-002",
                        title="Renderer",
                        owner_agent="claude",
                        status="running",
                        current_executor="claude",
                    ),
                    WorkPackageSnapshot(
                        id="WP-003",
                        title="Validation",
                        owner_agent="",
                        status="pending",
                        dependencies=["WP-002"],
                    ),
                    WorkPackageSnapshot(
                        id="WP-004",
                        title="Adapter",
                        owner_agent="codex",
                        status="blocked",
                        repair_blocked_reason="missing token",
                        repair_attempt_count=2,
                        repair_max_attempts=2,
                    ),
                    WorkPackageSnapshot(
                        id="WP-005",
                        title="Docs",
                        owner_agent="codex",
                        status="pending",
                        dependencies=["WP-001"],
                        parallel_group=2,
                    ),
                    WorkPackageSnapshot(
                        id="WP-006",
                        title="Paused",
                        owner_agent="codex",
                        status="paused",
                    ),
                ],
                post_review_items=[
                    PostReviewActionSnapshot(
                        id="AI-001",
                        severity="high",
                        status="pending",
                        title="테스트 보강",
                    )
                ],
            )
        )
        await pilot.pause()

        inspector = screen.query_one(WorkflowInspector)
        assert "작업 패키지 6개 · 완료 1 · 실행 1 · 대기 2 · 막힘 1 · 알 수 없음 1" in str(
            inspector.query_one("#inspector-progress").content
        )
        next_content = str(inspector.query_one("#inspector-next").content)
        assert "WP-005 Codex · Docs · 그룹 2" in next_content
        assert "WP-003 미지정 · Validation" in next_content
        assert "대기: WP-002" in next_content
        assert "복구 2/2 · missing token" in str(
            inspector.query_one("#inspector-blocked").content
        )
        assert "AI-001 [높음/대기] 테스트 보강" in str(
            inspector.query_one("#inspector-post-review").content
        )
        workflow_content = str(inspector.query_one("#inspector-workflow").content)
        assert "상태: 설계 준비" in workflow_content
        assert "라운드: 1" in workflow_content

        screen.apply_snapshot(
            WorkflowNexusSnapshot(
                state="idle",
                providers=[
                    ProviderSnapshot(
                        name="codex",
                        provider="codex",
                        enabled=True,
                        status="Ready",
                    )
                ],
            )
        )
        await pilot.pause()

        workflow_content = str(inspector.query_one("#inspector-workflow").content)
        provider_content = str(inspector.query_one("#inspector-providers").content)
        assert "ID: (새 워크플로우)" in workflow_content
        assert "codex: 기본값; 컨텍스트 알 수 없음 (알 수 없음); 세션 없음" in (
            provider_content
        )


@pytest.mark.asyncio
async def test_workflow_inspector_skips_repeated_section_updates(
    tmp_path,
    monkeypatch,
) -> None:
    updates: list[str | None] = []
    original_update = Static.update

    def counted_update(self, *args, **kwargs):
        updates.append(self.id)
        return original_update(self, *args, **kwargs)

    monkeypatch.setattr(Static, "update", counted_update)
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-inspector-cache",
        state="executing",
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Renderer",
                owner_agent="claude",
                status="running",
            )
        ],
        execution_log=["state_changed: executing"],
    )

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        inspector = app.screen.query_one(WorkflowInspector)

        inspector.apply_snapshot(snapshot)
        await pilot.pause()
        updates.clear()

        inspector.apply_snapshot(snapshot)
        await pilot.pause()

        inspector_updates = [
            item for item in updates if item and item.startswith("inspector-")
        ]
        assert inspector_updates == []

        inspector.apply_snapshot(
            WorkflowNexusSnapshot(
                session_id="wf-inspector-cache",
                state="executing",
                work_package_details=list(snapshot.work_package_details),
                execution_log=["state_changed: reviewing"],
            )
        )
        await pilot.pause()

        inspector_updates = [
            item for item in updates if item and item.startswith("inspector-")
        ]
        assert inspector_updates == ["inspector-log"]


@pytest.mark.asyncio
async def test_provider_inspector_modal_opens_from_nexus(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)
        screen.action_open_inspector()
        await pilot.pause()

        assert isinstance(app.screen, ProviderInspector)
        assert app.screen.query_one("#inspect-claude")


@pytest.mark.asyncio
async def test_providers_slash_command_opens_provider_inspector(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._handle_textual_slash_command("/providers")
        await pilot.pause()

        assert isinstance(app.screen, ProviderInspector)
        assert app.screen.query_one("#inspect-claude")


@pytest.mark.asyncio
async def test_provider_inspector_modal_uses_korean_chrome(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(
            ProviderInspector(
                [
                    ProviderSnapshot(
                        name="codex",
                        provider="codex",
                        enabled=True,
                        status="Ready",
                    )
                ],
                lang="ko",
            )
        )
        await pilot.pause()

        assert str(app.screen.query_one("#provider-inspector-title", Static).content) == (
            "프로바이더 인스펙터"
        )
        assert str(app.screen.query_one("#close-provider-inspector", Button).label) == (
            "닫기"
        )
        assert provider_inspector_label("all", lang="ko") == "전체"
        output = app.screen.query_one("#inspect-codex .provider-inspector-output", RichLog)
        text = "\n".join(line.text for line in output.lines)
        assert "아직 캡처된 원본 출력이 없습니다." in text


@pytest.mark.asyncio
async def test_provider_inspector_all_tab_wraps_long_output(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(80, 40)) as pilot:
        app.push_screen(
            ProviderInspector(
                [
                    ProviderSnapshot(
                        name="claude",
                        provider="claude-code",
                        enabled=True,
                        status="Ready",
                        raw_output="x" * 180,
                    )
                ]
            )
        )
        await pilot.pause()

        tabs = app.screen.query_one("#provider-inspector-tabs", TabbedContent)
        tabs.active = "inspect-all"
        await pilot.pause()

        output = app.screen.query_one("#inspect-all .provider-inspector-output", RichLog)
        content_width = output.scrollable_content_region.width
        assert output.wrap is True
        assert output.min_width == 1
        assert output.styles.height.value == 1
        assert len(output.lines) > 1
        assert max(line.cell_length for line in output.lines) <= content_width


@pytest.mark.asyncio
async def test_provider_inspector_pretty_prints_json_output(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(
            ProviderInspector(
                [
                    ProviderSnapshot(
                        name="codex",
                        provider="codex",
                        enabled=True,
                        status="Ready",
                        raw_output='{"name":"Trinity","items":[{"id":1,"label":"alpha"}]}',
                    )
                ]
            )
        )
        await pilot.pause()

        output = app.screen.query_one("#inspect-codex .provider-inspector-output", RichLog)
        assert "\n".join(line.text for line in output.lines) == (
            "{\n"
            '  "name": "Trinity",\n'
            '  "items": [\n'
            "    {\n"
            '      "id": 1,\n'
            '      "label": "alpha"\n'
            "    }\n"
            "  ]\n"
            "}"
        )


@pytest.mark.asyncio
async def test_provider_inspector_truncates_large_raw_output(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(
            ProviderInspector(
                [
                    ProviderSnapshot(
                        name="codex",
                        provider="codex",
                        enabled=True,
                        status="Ready",
                        raw_output=("head-" + ("x" * 59_990) + "-tail"),
                    )
                ]
            )
        )
        await pilot.pause()

        output = app.screen.query_one("#inspect-codex .provider-inspector-output", RichLog)
        text = "\n".join(line.text for line in output.lines)
        assert "[truncated 10000 characters" in text
        assert "head-" not in text
        assert "-tail" in text
        assert len(text) < 51_000


@pytest.mark.asyncio
async def test_provider_inspector_localizes_korean_truncation_marker(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path, lang="ko"))

    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(
            ProviderInspector(
                [
                    ProviderSnapshot(
                        name="codex",
                        provider="codex",
                        enabled=True,
                        status="Ready",
                        raw_output=("head-" + ("x" * 59_990) + "-tail"),
                    )
                ],
                lang="ko",
            )
        )
        await pilot.pause()

        output = app.screen.query_one("#inspect-codex .provider-inspector-output", RichLog)
        text = "\n".join(line.text for line in output.lines)
        assert "10000자 생략됨" in text
        assert "전체 출력은 원본 아티팩트에서 확인하세요" in text
        assert "[truncated" not in text
        assert "head-" not in text
        assert "-tail" in text


@pytest.mark.asyncio
async def test_provider_inspector_reads_raw_output_path_lazily(tmp_path) -> None:
    raw_path = tmp_path / "codex.raw.txt"
    raw_path.write_text("raw artifact body", encoding="utf-8")
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(
            ProviderInspector(
                [
                    ProviderSnapshot(
                        name="codex",
                        provider="codex",
                        enabled=True,
                        status="Ready",
                        summary="summary only",
                        raw_output_path=str(raw_path),
                    )
                ]
            )
        )
        await pilot.pause()

        output = app.screen.query_one("#inspect-codex .provider-inspector-output", RichLog)
        text = "\n".join(line.text for line in output.lines)
        assert "raw artifact body" in text
        assert "summary only" not in text


@pytest.mark.asyncio
async def test_provider_inspector_bounds_large_raw_output_path(tmp_path) -> None:
    raw_path = tmp_path / "codex-large.raw.txt"
    raw_path.write_text("head-" + ("x" * 59_990) + "-tail", encoding="utf-8")
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(
            ProviderInspector(
                [
                    ProviderSnapshot(
                        name="codex",
                        provider="codex",
                        enabled=True,
                        status="Ready",
                        raw_output_path=str(raw_path),
                    )
                ]
            )
        )
        await pilot.pause()

        output = app.screen.query_one("#inspect-codex .provider-inspector-output", RichLog)
        text = "\n".join(line.text for line in output.lines)
        assert "[truncated" in text
        assert "head-" not in text
        assert "-tail" in text
        assert len(text) <= 51_000


@pytest.mark.asyncio
async def test_provider_inspector_localizes_korean_raw_path_truncation(tmp_path) -> None:
    raw_path = tmp_path / "codex-large.raw.txt"
    raw_path.write_text("head-" + ("x" * 59_990) + "-tail", encoding="utf-8")
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path, lang="ko"))

    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(
            ProviderInspector(
                [
                    ProviderSnapshot(
                        name="codex",
                        provider="codex",
                        enabled=True,
                        status="Ready",
                        raw_output_path=str(raw_path),
                    )
                ],
                lang="ko",
            )
        )
        await pilot.pause()

        output = app.screen.query_one("#inspect-codex .provider-inspector-output", RichLog)
        text = "\n".join(line.text for line in output.lines)
        assert "바이트 중 마지막" in text
        assert "전체 출력은 원본 아티팩트" in text
        assert "확인하세요" in text
        assert "[truncated" not in text
        assert "head-" not in text
        assert "-tail" in text


@pytest.mark.asyncio
async def test_start_workspace_command_opens_workspace_picker(tmp_path) -> None:
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path),
        FakeWorkflowController(),
        launch_cwd=tmp_path,
    )

    async with app.run_test(size=(140, 44)) as pilot:
        app._handle_textual_slash_command("/workspace")
        await pilot.pause()

        assert isinstance(app.screen, WorkspacePicker)
        picker = app.screen
        assert picker.intent == "select"
        assert str(picker.query_one("#workspace-picker-title", Static).content) == (
            "Select Workspace"
        )
        assert str(picker.query_one("#confirm-execute", Button).label) == "Use Workspace"


@pytest.mark.asyncio
async def test_start_workspace_button_opens_workspace_picker(tmp_path) -> None:
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path),
        FakeWorkflowController(),
        launch_cwd=tmp_path,
    )

    async with app.run_test(size=(140, 44)) as pilot:
        start = app.screen
        assert isinstance(start, StartScreen)
        start.query_one("#start-select-workspace", Button).press()
        await pilot.pause()

        assert isinstance(app.screen, WorkspacePicker)
        picker = app.screen
        assert picker.intent == "select"
        assert str(picker.query_one("#workspace-picker-title", Static).content) == (
            "Select Workspace"
        )


@pytest.mark.asyncio
async def test_start_workspace_command_updates_workspace_candidate(tmp_path) -> None:
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path),
        FakeWorkflowController(),
        launch_cwd=tmp_path,
    )

    async with app.run_test(size=(140, 44)) as pilot:
        app._handle_textual_slash_command("/workspace")
        await pilot.pause()
        picker = app.screen
        assert isinstance(picker, WorkspacePicker)

        picker.action_confirm()
        await pilot.pause()

        start = app.get_screen("start", StartScreen)
        assert app.workspace_candidate == tmp_path
        assert str(tmp_path) in str(start.query_one("#workspace-candidate").content)
        assert load_project_intake(app.config.effective_state_dir) is None
        with pytest.raises(NoMatches):
            start.query_one("#project-intake-summary", Static)


def test_project_command_rejects_workspace_shortcut(
    tmp_path,
    monkeypatch,
) -> None:
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path),
        FakeWorkflowController(),
        launch_cwd=tmp_path,
    )
    results: list[tuple[str, str, str, str]] = []
    monkeypatch.setattr(
        app,
        "_record_slash_command_result",
        lambda command, title, body, **kwargs: results.append(
            (command, title, body, str(kwargs.get("severity", "")))
        ),
    )

    app._handle_textual_project_command("/project", ["workspace"])

    assert results == [
        (
            "/project",
            "Project Command Takes No Arguments",
            (
                "`/project workspace` is not supported.\n\n"
                "Use `/target <path>` to set a target or `/workspace` to browse."
            ),
            "warning",
        )
    ]


@pytest.mark.asyncio
async def test_start_workspace_label_keeps_stable_dimension(tmp_path) -> None:
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path),
        FakeWorkflowController(),
        launch_cwd=tmp_path,
    )

    async with app.run_test(size=(80, 30)) as pilot:
        await pilot.pause()
        start = app.get_screen("start", StartScreen)

        assert start.query_one("#workspace-candidate", Static).styles.height.value == 1


@pytest.mark.asyncio
async def test_start_new_project_submit_bypasses_generation_confirmation(
    tmp_path,
) -> None:
    control_repo = tmp_path / "control"
    target = tmp_path / "new-app"
    control_repo.mkdir()
    target.mkdir()
    config = TrinityConfig.default_config(project_dir=control_repo)
    write_project_intake(
        config.effective_state_dir,
        build_project_intake(
            mode="new",
            target_workspace=target,
            product_goal="Build a planning board.",
            project_type="textual app",
            starter_profile="textual-dashboard",
            target_users="operators",
            success_criteria="Operators can plan weekly work.",
            stack_preferences=("python", "textual"),
            first_milestone="First board workflow.",
            validation_commands=("uv run pytest",),
            constraints=("No external service",),
        ),
    )
    controller = FakeWorkflowController()
    app = TrinityTextualApp(config, controller, launch_cwd=target)

    async with app.run_test(size=(140, 44)) as pilot:
        start = app.get_screen("start", StartScreen)
        composer = start.query_one(PromptComposer)
        composer.set_text("Plan the first scaffold.")
        composer.action_submit()
        await pilot.pause()

        assert controller.started_prompts == ["Plan the first scaffold."]
        assert controller.target_workspace == target.resolve()
        intake = load_project_intake(app.config.effective_state_dir)
        assert intake is not None
        assert intake.mode == "new"
        assert intake.starter_profile == "textual-dashboard"
        assert intake.validation_commands == ("uv run pytest",)
        assert app.current_route == "nexus"
        assert isinstance(app.screen, NexusScreen)


@pytest.mark.asyncio
async def test_start_incomplete_new_project_submit_starts_directly(
    tmp_path,
) -> None:
    control_repo = tmp_path / "control"
    target = tmp_path / "new-app"
    control_repo.mkdir()
    target.mkdir()
    config = TrinityConfig.default_config(project_dir=control_repo)
    write_project_intake(
        config.effective_state_dir,
        build_project_intake(
            mode="new",
            target_workspace=target,
            product_goal="Build a planning board.",
            project_type="textual app",
            target_users="operators",
            success_criteria="Operators can plan weekly work.",
            first_milestone="First board workflow.",
        ),
    )
    controller = FakeWorkflowController()
    app = TrinityTextualApp(config, controller, launch_cwd=target)

    async with app.run_test(size=(140, 44)) as pilot:
        start = app.get_screen("start", StartScreen)
        composer = start.query_one(PromptComposer)
        composer.set_text("Plan the first scaffold.")
        composer.action_submit()
        await pilot.pause()

        assert controller.started_prompts == ["Plan the first scaffold."]
        assert controller.target_workspace == target.resolve()
        assert app.current_route == "nexus"
        assert isinstance(app.screen, NexusScreen)


@pytest.mark.asyncio
async def test_start_selected_workspace_overrides_launch_cwd_on_submit(
    tmp_path,
) -> None:
    controller = FakeWorkflowController()
    control_repo = tmp_path / "control"
    launch_cwd = tmp_path / "launch-cwd"
    selected = tmp_path / "selected-target"
    control_repo.mkdir()
    launch_cwd.mkdir()
    selected.mkdir()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=control_repo),
        controller,
        launch_cwd=launch_cwd,
    )

    async with app.run_test(size=(140, 44)) as pilot:
        app._handle_textual_slash_command("/workspace")
        await pilot.pause()
        picker = app.screen
        assert isinstance(picker, WorkspacePicker)
        picker.query_one("#workspace-path-input", Input).value = str(selected)
        picker.action_confirm()
        await pilot.pause()

        start = app.get_screen("start", StartScreen)
        assert str(selected) in str(start.query_one("#workspace-candidate").content)

        composer = start.query_one(PromptComposer)
        composer.set_text("선택한 폴더에서 작업해줘")
        composer.action_submit()
        await pilot.pause()

        assert controller.target_workspace == selected.resolve()
        assert controller.target_workspace != launch_cwd.resolve()
        assert app.confirmed_preflight is not None
        assert app.confirmed_preflight.path == selected.resolve()
        nexus = app.get_screen("nexus", NexusScreen)
        assert str(selected.resolve()) in str(
            nexus.query_one("#nexus-target-workspace", Static).content
        )


@pytest.mark.asyncio
async def test_nexus_workspace_command_selects_target_without_execution(
    tmp_path,
) -> None:
    control_repo = tmp_path / "control"
    target = tmp_path / "target-app"
    control_repo.mkdir()
    target.mkdir()
    (target / "README.md").write_text("# Existing project\n", encoding="utf-8")
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(session_id="wf-fake", state="idle")
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=control_repo),
        controller,
        launch_cwd=target,
    )

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        nexus = app.screen
        assert isinstance(nexus, NexusScreen)
        workspace_label = nexus.query_one("#nexus-target-workspace", Static)
        assert str(target.resolve()) in str(workspace_label.content)
        assert workspace_label.styles.min_width.value == 0
        assert workspace_label.styles.height.value == 1
        assert workspace_label.styles.content_align_vertical == "middle"

        app._handle_textual_slash_command("/workspace")
        await pilot.pause()

        assert controller.execution_requests == 0
        picker = app.screen
        assert isinstance(picker, WorkspacePicker)
        assert picker.intent == "select"
        assert str(picker.query_one("#workspace-picker-title", Static).content) == (
            "Select Workspace"
        )

        picker.action_confirm()
        await pilot.pause()

        assert controller.execution_requests == 0
        assert controller.target_workspace == target.resolve()
        assert app.current_route == "nexus"


@pytest.mark.asyncio
async def test_nexus_workspace_label_stays_within_narrow_width(tmp_path) -> None:
    control_repo = tmp_path / "control"
    target = tmp_path / "target-app-with-a-very-long-directory-name"
    control_repo.mkdir()
    target.mkdir()
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(session_id="wf-fake", state="idle")
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=control_repo),
        controller,
        launch_cwd=target,
    )

    async with app.run_test(size=(80, 36)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        nexus = app.screen
        assert isinstance(nexus, NexusScreen)
        widgets = (
            nexus.query_one("#nexus-target-workspace", Static),
        )
        for widget in widgets:
            assert widget.region.x >= 0
            assert widget.region.x + widget.region.width <= nexus.size.width


@pytest.mark.parametrize("size", [(60, 20), (80, 24)])
@pytest.mark.asyncio
async def test_nexus_screen_stays_within_narrow_viewport(
    tmp_path,
    size: tuple[int, int],
) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=size) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        nexus = app.screen
        assert isinstance(nexus, NexusScreen)
        nexus_shell = nexus.query_one("#nexus-screen")
        widgets = (
            nexus.query_one("#provider-strip"),
            nexus.query_one("#nexus-target-workspace", Static),
            nexus.query_one("#nexus-main"),
            nexus.query_one("#nexus-recipient-selector"),
            nexus.query_one("#nexus-composer", PromptComposer),
        )
        for widget in widgets:
            assert widget.region.x >= 0
            assert widget.region.x + widget.region.width <= nexus.size.width
            assert widget.region.y >= nexus_shell.region.y
            assert (
                widget.region.y + widget.region.height
                <= nexus_shell.region.y + nexus_shell.region.height
            )


@pytest.mark.asyncio
async def test_nexus_command_palette_stays_within_narrow_viewport(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(80, 24)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        nexus = app.screen
        assert isinstance(nexus, NexusScreen)
        composer = nexus.query_one("#nexus-composer", PromptComposer)
        composer.set_text("/")
        await pilot.pause()

        nexus_shell = nexus.query_one("#nexus-screen")
        widgets = (
            composer,
            composer.query_one("#prompt-command-palette"),
        )
        for widget in widgets:
            assert widget.region.y >= nexus_shell.region.y
            assert (
                widget.region.y + widget.region.height
                <= nexus_shell.region.y + nexus_shell.region.height
            )


def test_nexus_safe_target_prefers_snapshot_target(tmp_path) -> None:
    control_repo = tmp_path / "control"
    stale_candidate = tmp_path / "stale"
    snapshot_target = tmp_path / "snapshot-target"
    control_repo.mkdir()
    stale_candidate.mkdir()
    snapshot_target.mkdir()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=control_repo),
        FakeWorkflowController(),
        launch_cwd=control_repo,
    )
    app.workspace_candidate = stale_candidate

    assert app._safe_nexus_target_workspace(
        WorkflowNexusSnapshot(target_workspace=str(snapshot_target))
    ) == snapshot_target


@pytest.mark.asyncio
async def test_nexus_select_workspace_inside_control_repo_requires_confirmation(
    tmp_path,
) -> None:
    control_repo = tmp_path / "control"
    control_repo.mkdir()
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(session_id="wf-fake", state="idle")
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=control_repo),
        controller,
    )
    preflight = build_preflight(
        control_repo,
        WorkflowNexusSnapshot(session_id="wf-fake", state="idle"),
    )

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._on_nexus_workspace_selected(preflight)
        await pilot.pause()

        assert isinstance(app.screen, TargetWorkspaceConfirmModal)
        assert controller.target_workspace is None

        app.screen.query_one("#confirm-target", Button).press()
        await pilot.pause()

        assert controller.execution_requests == 0
        assert controller.target_workspace == control_repo
        assert controller.target_control_confirmed is True


@pytest.mark.asyncio
async def test_nexus_workspace_label_skips_unchanged_update(
    tmp_path,
    monkeypatch,
) -> None:
    control_repo = tmp_path / "control"
    target = tmp_path / "target-app"
    next_target = tmp_path / "next-app"
    control_repo.mkdir()
    target.mkdir()
    next_target.mkdir()
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=control_repo),
        launch_cwd=target,
    )

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        nexus = app.screen
        assert isinstance(nexus, NexusScreen)
        workspace_label = nexus.query_one("#nexus-target-workspace", Static)
        nexus._refresh_workspace_label()
        updates: list[str] = []
        original_update = workspace_label.update

        def counted_update(content) -> None:
            updates.append(str(content))
            original_update(content)

        workspace_label.update = counted_update
        query_calls: list[str] = []
        original_query = nexus.query

        def counted_query(*args, **kwargs):
            query_calls.append(str(args[0]) if args else "")
            return original_query(*args, **kwargs)

        monkeypatch.setattr(nexus, "query", counted_query)

        nexus._refresh_workspace_label()
        await pilot.pause()
        assert updates == []
        assert "#nexus-target-workspace" not in query_calls

        nexus.set_workspace_candidate(next_target)
        await pilot.pause()

        assert updates == [f"Planning target: {next_target}"]


@pytest.mark.asyncio
async def test_nexus_action_bar_keeps_korean_workspace_label(tmp_path) -> None:
    control_repo = tmp_path / "control"
    target = tmp_path / "target-app"
    control_repo.mkdir()
    target.mkdir()
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(session_id="wf-fake", state="idle")
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=control_repo, lang="ko"),
        controller,
        launch_cwd=target,
    )

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        nexus = app.screen
        assert isinstance(nexus, NexusScreen)
        workspace_label = str(
            nexus.query_one("#nexus-target-workspace", Static).content
        )
        assert workspace_label.startswith("계획 대상: ")
        assert str(target.resolve()) in workspace_label
        assert nexus.query_one("#nexus-composer", PromptComposer).placeholder == (
            "답변, 방향 조정 또는 /로 명령 입력"
        )

    screen = NexusScreen(
        TrinityConfig.default_config(project_dir=control_repo, lang="ko")
    )
    assert screen.workspace_label() == "대상 작업 폴더 없음"


@pytest.mark.asyncio
async def test_nexus_execute_requests_execution_when_target_is_selected(
    tmp_path,
) -> None:
    target = tmp_path / "target-app"
    target.mkdir()
    (target / "README.md").write_text("# Target\n", encoding="utf-8")
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            session_id="wf-fake",
            state="blueprint_ready",
            target_workspace=str(target),
            work_package_details=[
                WorkPackageSnapshot(
                    id="WP-001",
                    title="Build CLI",
                    owner_agent="codex",
                    status="pending",
                )
            ],
        )
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path),
        controller,
        launch_cwd=target,
    )

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        nexus = app.screen
        assert isinstance(nexus, NexusScreen)

        nexus.action_request_execute()
        await pilot.pause()

        assert isinstance(app.screen, ExecutionConfirmModal)
        assert controller.execution_requests == 0
        summary = str(
            app.screen.query_one("#execution-confirm-summary", Static).content
        )
        assert "Target workspace" in summary
        assert "Project context: saved context: not recorded" in summary
        assert "Risks: none" in summary

        app.screen.action_confirm()
        await pilot.pause()

        assert controller.execution_requests == 1
        assert controller.execution_instructions == [""]


@pytest.mark.asyncio
async def test_nexus_execute_confirmation_shows_workspace_risks(
    tmp_path,
) -> None:
    control_repo = tmp_path / "control"
    target = tmp_path / "target-app"
    control_repo.mkdir()
    target.mkdir()
    subprocess.run(
        ["git", "init"],
        cwd=target,
        check=True,
        capture_output=True,
        text=True,
    )
    intake = build_project_intake(
        mode="existing",
        target_workspace=target,
        created_at="2000-01-01T00:00:00Z",
    )
    config = TrinityConfig.default_config(project_dir=control_repo)
    write_project_intake(config.effective_state_dir, intake)
    (target / "scratch.txt").write_text("pending work\n", encoding="utf-8")
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            session_id="wf-fake",
            state="blueprint_ready",
            target_workspace=str(target),
            work_package_details=[
                WorkPackageSnapshot(
                    id="WP-001",
                    title="Build CLI",
                    owner_agent="codex",
                    status="pending",
                )
            ],
        )
    )
    app = TrinityTextualApp(config, controller, launch_cwd=target)

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        nexus = app.screen
        assert isinstance(nexus, NexusScreen)
        nexus.action_request_execute()
        await pilot.pause()

        assert isinstance(app.screen, ExecutionConfirmModal)
        summary = str(
            app.screen.query_one("#execution-confirm-summary", Static).content
        )
        assert "Workspace context: recorded" in summary
        assert "Project context:" in summary
        assert "scope: target root" in summary
        assert "validation: missing" in summary
        assert "Risks: dirty Git workspace" in summary
        assert "1 untracked" in summary
        assert "saved analysis stale" in summary


@pytest.mark.asyncio
async def test_nexus_execute_confirmation_cancel_leaves_execution_untouched(
    tmp_path,
) -> None:
    target = tmp_path / "target-app"
    target.mkdir()
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            session_id="wf-fake",
            state="blueprint_ready",
            target_workspace=str(target),
            work_package_details=[
                WorkPackageSnapshot(
                    id="WP-001",
                    title="Build CLI",
                    owner_agent="codex",
                    status="pending",
                )
            ],
        )
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path),
        controller,
        launch_cwd=target,
    )

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        nexus = app.screen
        assert isinstance(nexus, NexusScreen)
        nexus.action_request_execute()
        await pilot.pause()

        assert isinstance(app.screen, ExecutionConfirmModal)
        app.screen.action_cancel()
        await pilot.pause()

        assert controller.execution_requests == 0
        assert controller.execution_instructions == []


@pytest.mark.asyncio
async def test_nexus_execute_slash_command_uses_confirmation(
    tmp_path,
) -> None:
    target = tmp_path / "target-app"
    target.mkdir()
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            session_id="wf-fake",
            state="blueprint_ready",
            target_workspace=str(target),
            work_package_details=[
                WorkPackageSnapshot(
                    id="WP-001",
                    title="Build CLI",
                    owner_agent="codex",
                    status="pending",
                )
            ],
        )
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path),
        controller,
        launch_cwd=target,
    )

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._handle_textual_slash_command("/execute focus cli")
        await pilot.pause()

        assert isinstance(app.screen, ExecutionConfirmModal)
        assert controller.execution_requests == 0
        assert "Instruction: focus cli" in str(
            app.screen.query_one("#execution-confirm-summary", Static).content
        )

        app.screen.action_confirm()
        await pilot.pause()

        assert controller.execution_requests == 1
        assert controller.execution_instructions == ["focus cli"]


@pytest.mark.asyncio
async def test_nexus_question_answer_routes_to_controller(tmp_path) -> None:
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            questions=[QuestionSnapshot(id="q-1", question="Theme?", options=["dark"])]
        )
    )
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        app.screen.query_one(QuestionPanel).apply_questions(controller.snapshot().questions)
        button = app.screen.query_one("#answer-q-1-1", Button)
        button.press()
        await pilot.pause()

        assert controller.answers == [("q-1", "dark", False)]


@pytest.mark.asyncio
async def test_nexus_question_answer_handles_non_ascii_question_id(tmp_path) -> None:
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            questions=[
                QuestionSnapshot(
                    id="메타플레이",
                    question="실시간 메타플레이가 필요한가?",
                    options=["정적 전용으로 시작한다"],
                )
            ]
        )
    )
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        app.screen.query_one(QuestionPanel).apply_questions(controller.snapshot().questions)
        button = app.screen.query_one("#answer-q-1-1", Button)
        button.press()
        await pilot.pause()

        assert button.id == "answer-q-1-1"
        assert controller.answers == [("메타플레이", "정적 전용으로 시작한다", False)]


@pytest.mark.asyncio
async def test_workspace_picker_opens_from_nexus_execute(tmp_path) -> None:
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(target_workspace=str(tmp_path))
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path),
        controller,
        launch_cwd=tmp_path,
    )

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)
        screen.action_request_execute()
        await pilot.pause()

        assert isinstance(app.screen, WorkspacePicker)
        assert app.screen.intent == "execute"
        assert controller.execution_requests == 1
        assert str(tmp_path) in str(app.screen.query_one("#workspace-preflight").content)


@pytest.mark.asyncio
async def test_execution_matrix_renders_preflight_and_packages(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecutionMatrixScreen)
        screen.apply_execution_state(
            build_preflight(tmp_path, WorkflowNexusSnapshot()),
            WorkflowNexusSnapshot(
                work_packages=["WP-001 codex: Build Textual shell (pending)"],
                execution_log=["package WP-001 queued"],
            ),
        )
        await pilot.pause()

        assert str(tmp_path) in str(screen.query_one("#execution-header").content)
        rows = screen.query("#execution-package-list .execution-package-row")
        assert len(rows) == 1
        assert "WAIT" in _widget_tree_text(rows.first())


@pytest.mark.asyncio
async def test_execution_matrix_header_uses_snapshot_target_without_preflight(
    tmp_path,
) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))
    target = tmp_path / "snapshot-target"
    target.mkdir()

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecutionMatrixScreen)
        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(target_workspace=str(target)),
        )
        await pilot.pause()

        assert str(target) in str(screen.query_one("#execution-header").content)


@pytest.mark.asyncio
async def test_execution_matrix_retry_button_opens_retry_modal(tmp_path) -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-retry-action",
        goal="game",
        state="failed",
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Client",
                owner_agent="codex",
                status="failed",
                retryable=True,
            ),
            WorkPackageSnapshot(
                id="WP-002",
                title="Docs",
                owner_agent="claude",
                status="done",
                retryable=False,
            ),
        ],
    )
    controller = FakeWorkflowController(snapshot)
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecutionMatrixScreen)
        screen.apply_execution_state(None, snapshot)
        await pilot.pause()

        retry_button = screen.query_one("#execution-retry", Button)
        assert str(retry_button.label) == "Retry 1"
        assert retry_button.disabled is False

        retry_button.press()
        await pilot.pause()

        assert isinstance(app.screen, ExecutionRetryModal)
        assert controller.retry_previews == [("all", [])]


@pytest.mark.asyncio
async def test_execution_matrix_row_retry_button_opens_custom_retry_modal(
    tmp_path,
) -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-row-retry",
        goal="game",
        state="failed",
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Client",
                owner_agent="codex",
                status="failed",
                retryable=True,
            ),
            WorkPackageSnapshot(
                id="WP-002",
                title="Docs",
                owner_agent="claude",
                status="done",
                retryable=False,
            ),
        ],
    )
    controller = FakeWorkflowController(snapshot)
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecutionMatrixScreen)
        screen.apply_execution_state(None, snapshot)
        await pilot.pause()

        assert str(screen.query_one("#wp-detail-0", Button).label) == "Spec"
        retry_button = screen.query_one("#wp-retry-0", Button)
        assert str(retry_button.label) == "Retry"
        assert not screen.query("#wp-retry-1")

        retry_button.press()
        await pilot.pause()

        assert controller.retry_previews == [("custom", ["WP-001"])]
        assert isinstance(app.screen, ExecutionRetryModal)
        assert app.screen.selector == "custom"
        assert app.screen.selected_ids == {"WP-001"}


@pytest.mark.asyncio
async def test_execution_matrix_retry_button_disables_without_candidates(
    tmp_path,
) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("execution")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecutionMatrixScreen)
        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(
                work_package_details=[
                    WorkPackageSnapshot(
                        id="WP-001",
                        title="Docs",
                        owner_agent="claude",
                        status="done",
                        retryable=False,
                    ),
                ],
            ),
        )
        await pilot.pause()

        retry_button = screen.query_one("#execution-retry", Button)
        assert str(retry_button.label) == "Retry"
        assert retry_button.disabled is True


@pytest.mark.asyncio
async def test_settings_screen_saves_theme_preferences(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("settings")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SettingsScreen)

        assert app.theme == "textual-dark"
        screen.query_one("#theme-mode").value = "light"
        screen.query_one("#density").value = "compact"
        screen.action_apply()
        await pilot.pause()

        assert app.theme == "textual-light"

    saved = UISettingsStore(tmp_path / ".trinity").load()
    assert saved.theme_mode == "light"
    assert saved.density == "compact"


def test_textual_app_applies_saved_theme_on_startup(tmp_path) -> None:
    UISettingsStore(tmp_path / ".trinity").save(UISettings(theme_mode="light"))

    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    assert app.theme == "textual-light"


@pytest.mark.asyncio
async def test_textual_app_applies_saved_color_profile_on_startup(tmp_path) -> None:
    UISettingsStore(tmp_path / ".trinity").save(UISettings(color_profile="256color"))
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()

        assert app.has_class("ui-color-profile-256color")
        assert not app.has_class("ui-color-profile-truecolor")
        assert not app.has_class("ui-color-profile-ascii-safe")


@pytest.mark.asyncio
async def test_textual_app_applies_saved_density_and_motion_on_startup(tmp_path) -> None:
    UISettingsStore(tmp_path / ".trinity").save(
        UISettings(density="compact", motion="reduced")
    )
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        animation = app.screen.query_one(SacredGeometryAnimation)
        angle = animation._angle

        animation._tick()

        assert app.has_class("ui-density-compact")
        assert app.has_class("ui-motion-reduced")
        assert animation._angle == angle


@pytest.mark.asyncio
async def test_textual_app_applies_saved_unicode_rendering_on_startup(tmp_path) -> None:
    UISettingsStore(tmp_path / ".trinity").save(UISettings(unicode_rendering="unicode"))
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        animation = app.screen.query_one(SacredGeometryAnimation)

        assert app.has_class("ui-unicode-rendering")
        assert animation._render_mode == "unicode"


@pytest.mark.asyncio
async def test_settings_screen_applies_density_and_motion_preferences(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("settings")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SettingsScreen)

        screen.query_one("#density").value = "compact"
        screen.query_one("#motion").value = "reduced"
        screen.action_apply()
        await pilot.pause()

        assert app.has_class("ui-density-compact")
        assert app.has_class("ui-motion-reduced")

        screen.query_one("#density").value = "comfortable"
        screen.query_one("#motion").value = "normal"
        screen.action_apply()
        await pilot.pause()

        assert not app.has_class("ui-density-compact")
        assert not app.has_class("ui-motion-reduced")


@pytest.mark.asyncio
async def test_settings_screen_applies_color_profile_preference(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("settings")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SettingsScreen)

        screen.query_one("#color-profile").value = "truecolor"
        screen.action_apply()
        await pilot.pause()
        preview = str(screen.query_one("#theme-preview", Static).content)

        assert app.has_class("ui-color-profile-truecolor")
        assert not app.has_class("ui-color-profile-256color")
        assert not app.has_class("ui-color-profile-ascii-safe")
        assert (
            "Color profile: truecolor · Logo motion: normal · "
            "Logo glyphs: ascii"
        ) in preview

        screen.query_one("#color-profile").value = "ascii-safe"
        screen.action_apply()
        await pilot.pause()
        preview = str(screen.query_one("#theme-preview", Static).content)

        assert app.has_class("ui-color-profile-ascii-safe")
        assert not app.has_class("ui-color-profile-256color")
        assert not app.has_class("ui-color-profile-truecolor")
        assert (
            "Color profile: ascii-safe · Logo motion: normal · "
            "Logo glyphs: ascii"
        ) in preview

        screen.query_one("#color-profile").value = "auto"
        screen.action_apply()
        await pilot.pause()

        assert not app.has_class("ui-color-profile-ascii-safe")
        assert not app.has_class("ui-color-profile-256color")
        assert not app.has_class("ui-color-profile-truecolor")


@pytest.mark.asyncio
async def test_settings_visual_preferences_reach_settings_and_nexus_surfaces(
    tmp_path,
) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("settings")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SettingsScreen)

        preview = screen.query_one("#theme-preview", Static)
        screen.query_one("#color-profile").value = "truecolor"
        screen.query_one("#density").value = "compact"
        screen.action_apply()
        await pilot.pause()

        assert app.has_class("ui-color-profile-truecolor")
        assert app.has_class("ui-density-compact")
        assert preview.is_mounted

        app.switch_to("nexus")
        await pilot.pause()
        nexus = app.screen
        assert isinstance(nexus, NexusScreen)

        assert app.has_class("ui-color-profile-truecolor")
        assert app.has_class("ui-density-compact")
        assert nexus.query_one("#provider-strip").is_mounted
        assert nexus.query_one("#nexus-composer", PromptComposer).is_mounted


@pytest.mark.asyncio
async def test_settings_controls_use_flexible_width(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("settings")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SettingsScreen)
        preview = screen.query_one("#theme-preview", Static)
        model_select = screen.query_one("#model-claude", Select)

        assert preview.styles.height.is_auto
        assert not preview.styles.width.is_cells
        assert model_select.styles.width.is_fraction


@pytest.mark.asyncio
async def test_settings_screen_applies_unicode_rendering_preference(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        start_animation = app.screen.query_one(SacredGeometryAnimation)
        assert start_animation._render_mode == "ascii"

        app.switch_to("settings")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SettingsScreen)

        screen.query_one("#unicode-rendering").value = "unicode"
        screen.action_apply()
        await pilot.pause()

        assert app.has_class("ui-unicode-rendering")
        assert start_animation._render_mode == "unicode"
        app.switch_to("start")
        await pilot.pause()
        assert start_animation._render_mode == "unicode"

        app.switch_to("settings")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SettingsScreen)
        screen.query_one("#unicode-rendering").value = "ascii"
        screen.action_apply()
        await pilot.pause()

        assert not app.has_class("ui-unicode-rendering")
        assert start_animation._render_mode == "ascii"
        app.switch_to("start")
        await pilot.pause()
        assert start_animation._render_mode == "ascii"


@pytest.mark.asyncio
async def test_settings_preview_shows_profile_output_contracts(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("settings")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SettingsScreen)

        preview = str(screen.query_one("#theme-preview", Static).content)

        assert "contracts execute:execution_v1 review:review_v1" in preview


@pytest.mark.asyncio
async def test_settings_screen_uses_korean_preview_labels(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    app = TrinityTextualApp(config)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("settings")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SettingsScreen)

        preview = str(screen.query_one("#theme-preview", Static).content)

        assert screen.label_text("central_provider") == "중앙 프로바이더"
        assert "테마 모드: 다크" in preview
        assert "밀도: 여유" in preview
        assert (
            "색상 프로필: 기본 팔레트 · 로고 애니메이션: 기본 · "
            "로고 글리프: ASCII"
        ) in preview
        assert "중앙: 자동 / 강력" in preview
        assert "Claude: 기본값" in preview
        assert "Claude: 기본값 · 설계자 · 아키텍처 0.95" in preview
        assert "출력 형식 실행:실행 v1 리뷰:리뷰 v1" in preview
        assert "Mode:" not in preview
        assert "Density:" not in preview
        assert "Color profile:" not in preview
        assert "Motion:" not in preview
        assert "Unicode:" not in preview
        assert "Central:" not in preview
        assert "architecture 0.95" not in preview
        assert "테마 모드: system" not in preview
        assert "밀도: comfortable" not in preview
        assert "Claude: default" not in preview
        assert "contracts " not in preview


@pytest.mark.asyncio
async def test_settings_screen_saves_agent_and_central_models(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    app = TrinityTextualApp(config)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("settings")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SettingsScreen)

        screen.query_one("#model-claude").value = "sonnet[1m]"
        screen.query_one("#model-codex").value = "gpt-5"
        screen.query_one("#central-provider").value = "codex"
        screen.query_one("#central-model").value = "agent-default"
        screen.action_apply()
        await pilot.pause()

    saved_config = TrinityConfig.load(tmp_path / ".trinity" / "trinity.config")
    assert saved_config.agents["claude"].model == "sonnet[1m]"
    assert saved_config.agents["codex"].model == "gpt-5"
    assert saved_config.synthesis_agent == "codex"
    assert saved_config.synthesis_model == "agent-default"


@pytest.mark.asyncio
async def test_settings_screen_uses_discovered_model_choices(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    app = TrinityTextualApp(config)
    app._model_discovery_started = True
    spec = config.agents["claude"]
    discovered = (
        ProviderModelChoice(
            provider=spec.provider,
            model="default",
            label="claude(default)",
            source="static-fallback",
            is_default=True,
            context_budget=200_000,
        ),
        ProviderModelChoice(
            provider=spec.provider,
            model="opus-live",
            label="Opus Live",
            source="cli-live",
            context_budget=1_000_000,
        ),
    )

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app._apply_discovered_model_choices({"claude": discovered})
        app.switch_to("settings")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SettingsScreen)

        model_select = screen.query_one("#model-claude", Select)
        central_provider_select = screen.query_one("#central-provider", Select)
        central_select = screen.query_one("#central-model", Select)
        model_values = {value for _label, value in model_select._options}
        central_values = {value for _label, value in central_select._options}
        model_labels = {value: str(label) for label, value in model_select._options}
        central_provider_labels = {
            value: str(label) for label, value in central_provider_select._options
        }
        central_labels = {value: str(label) for label, value in central_select._options}
        assert "opus-live" in model_values
        assert "opus-live" in central_values
        assert central_provider_labels["claude"] == "Claude"
        assert model_labels["opus-live"] == "Opus Live  cli-live  1,000,000 ctx"
        assert central_labels["opus-live"] == "Opus Live  cli-live  1,000,000 ctx"

        model_select.value = "opus-live"
        screen.query_one("#central-provider").value = "claude"
        await pilot.pause()
        central_select = screen.query_one("#central-model", Select)
        central_select.value = "opus-live"
        screen.action_apply()
        await pilot.pause()
        preview = str(screen.query_one("#theme-preview", Static).content)

        assert "Claude: Opus Live  cli-live  1,000,000 ctx" in preview
        assert "Central: Claude / Opus Live  cli-live  1,000,000 ctx" in preview

    assert config.agents["claude"].model == "opus-live"
    assert config.synthesis_agent == "claude"
    assert config.synthesis_model == "opus-live"


@pytest.mark.asyncio
async def test_settings_preview_refreshes_when_model_choices_arrive(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents["claude"].model = "opus-live"
    config.synthesis_agent = "claude"
    config.synthesis_model = "opus-live"
    app = TrinityTextualApp(config)
    app._model_discovery_started = True
    spec = config.agents["claude"]
    discovered = (
        ProviderModelChoice(
            provider=spec.provider,
            model="opus-live",
            label="Opus Live",
            source="cli-live",
            context_budget=1_000_000,
        ),
    )

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("settings")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SettingsScreen)

        preview = str(screen.query_one("#theme-preview", Static).content)
        assert "Claude: opus-live" in preview
        assert "Central: Claude / opus-live" in preview

        app._apply_discovered_model_choices({"claude": discovered})
        await pilot.pause()
        preview = str(screen.query_one("#theme-preview", Static).content)

        assert "Claude: Opus Live  cli-live  1,000,000 ctx" in preview
        assert "Central: Claude / Opus Live  cli-live  1,000,000 ctx" in preview


@pytest.mark.asyncio
async def test_settings_central_models_follow_selected_provider(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    app = TrinityTextualApp(config)
    app._model_discovery_started = True
    claude = config.agents["claude"]
    codex = config.agents["codex"]
    discovered = {
        "claude": (
            ProviderModelChoice(
                provider=claude.provider,
                model="opus-live",
                label="Opus Live",
                source="cli-live",
            ),
        ),
        "codex": (
            ProviderModelChoice(
                provider=codex.provider,
                model="gpt-live",
                label="GPT Live",
                source="cli-live",
            ),
        ),
    }

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app._apply_discovered_model_choices(discovered)
        app.switch_to("settings")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SettingsScreen)

        central_provider = screen.query_one("#central-provider", Select)
        central_model = screen.query_one("#central-model", Select)
        auto_values = {value for _label, value in central_model._options}
        assert {"opus-live", "gpt-live"} <= auto_values

        central_provider.value = "claude"
        await pilot.pause()
        central_model = screen.query_one("#central-model", Select)
        claude_values = {value for _label, value in central_model._options}

        assert "opus-live" in claude_values
        assert "gpt-live" not in claude_values
        assert central_model.value == "agent-default"
        screen.action_apply()
        await pilot.pause()

    saved_config = TrinityConfig.load(tmp_path / ".trinity" / "trinity.config")
    assert saved_config.synthesis_agent == "claude"
    assert saved_config.synthesis_model == "agent-default"


@pytest.mark.asyncio
async def test_settings_central_model_label_prefers_selected_provider(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.synthesis_agent = "codex"
    config.synthesis_model = "shared-live"
    app = TrinityTextualApp(config)
    app._model_discovery_started = True
    claude = config.agents["claude"]
    codex = config.agents["codex"]
    discovered = {
        "claude": (
            ProviderModelChoice(
                provider=claude.provider,
                model="shared-live",
                label="Claude Shared",
                source="cli-live",
            ),
        ),
        "codex": (
            ProviderModelChoice(
                provider=codex.provider,
                model="shared-live",
                label="Codex Shared",
                source="cli-live",
            ),
        ),
    }

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app._apply_discovered_model_choices(discovered)
        app.switch_to("settings")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SettingsScreen)

        central_select = screen.query_one("#central-model", Select)
        central_labels = {value: str(label) for label, value in central_select._options}
        preview = str(screen.query_one("#theme-preview", Static).content)

        assert central_labels["shared-live"] == "Codex Shared  cli-live"
        assert "Central: Codex / Codex Shared  cli-live" in preview
        assert "Central: Codex / Claude Shared" not in preview


@pytest.mark.asyncio
async def test_settings_screen_syncs_mounted_agent_model_selectors(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    app = TrinityTextualApp(config)

    async with app.run_test(size=(120, 40)) as pilot:
        start = app.screen
        assert isinstance(start, StartScreen)
        assert (
            start.query_one(AgentRecipientModelSelector).selected_model("claude")
            == "default"
        )

        app.switch_to("nexus")
        await pilot.pause()
        nexus = app.screen
        assert isinstance(nexus, NexusScreen)
        assert (
            nexus.query_one(AgentRecipientModelSelector).selected_model("claude")
            == "default"
        )

        app.switch_to("settings")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SettingsScreen)

        screen.query_one("#model-claude").value = "sonnet[1m]"
        screen.query_one("#model-codex").value = "gpt-5"
        screen.action_apply()
        await pilot.pause()

        app.switch_to("start")
        await pilot.pause()
        start = app.screen
        assert isinstance(start, StartScreen)
        start_selector = start.query_one(AgentRecipientModelSelector)
        assert start_selector.selected_model("claude") == "sonnet[1m]"
        assert start_selector.selected_model("codex") == "gpt-5"

        app.switch_to("nexus")
        await pilot.pause()
        nexus = app.screen
        assert isinstance(nexus, NexusScreen)
        nexus_selector = nexus.query_one(AgentRecipientModelSelector)
        assert nexus_selector.selected_model("claude") == "sonnet[1m]"
        assert nexus_selector.selected_model("codex") == "gpt-5"


@pytest.mark.asyncio
async def test_nexus_renders_blueprint_action_buttons(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    app = TrinityTextualApp(config)

    async with app.run_test(size=(120, 40)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)

        screen.apply_snapshot(
            WorkflowNexusSnapshot(
                session_id="wf-blueprint",
                state="blueprint_ready",
                goal="게임 만들기",
                synthesis=SynthesisSnapshot(summary="설계 완료"),
                central_blueprint="중앙 에이전트 응답",
                work_packages=["WP-001 codex: 구현 (pending)"],
            )
        )
        await pilot.pause()

        assert len(screen.query("#central-actions Button")) == 4
        assert screen.query_one("#central-action-title", Static).content == "다음 작업"


@pytest.mark.asyncio
async def test_nexus_provider_error_gate_actions_answer_question(tmp_path) -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-provider-error",
        state="needs_user_decision",
        questions=[
            QuestionSnapshot(
                id="q-provider-error-retry",
                question="Provider errors occurred.",
                options=[
                    "Retry failed providers",
                    "Continue without failed providers",
                    "Stop workflow",
                ],
            )
        ],
    )
    controller = FakeWorkflowController(snapshot)
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)
        screen.apply_snapshot(controller.snapshot())
        await pilot.pause()

        assert screen.query_one("#central-action-title", Static).content == (
            "프로바이더 오류 결정"
        )
        buttons = list(screen.query("#central-actions Button"))
        assert [str(button.label) for button in buttons] == [
            "실패 재시도",
            "제외하고 계속",
            "중단",
        ]

        buttons[0].press()
        await pilot.pause()

    assert controller.answers == [
        ("q-provider-error-retry", "Retry failed providers", False)
    ]


def test_review_repair_details_markdown_summarizes_blocked_packages() -> None:
    snapshot = _review_repair_blocked_snapshot()

    assert review_repair_blocked_ids(snapshot) == ("WP-002",)
    assert review_repair_rows(snapshot) == (
        (
            "WP-002",
            "duplicate_required_changes; attempts=2/3; review=changes_requested",
        ),
    )

    body = review_repair_details_markdown(snapshot)

    assert "Review-repair loop guard has paused these work packages" in body
    assert "WP-002" in body
    assert "duplicate_required_changes" in body
    assert "Recent repair notes" in body


def test_review_repair_details_markdown_uses_korean_labels() -> None:
    snapshot = _review_repair_blocked_snapshot()

    assert review_repair_title(lang="ko") == "리뷰 보정"
    assert review_repair_action_hint(lang="ko") == (
        "중앙 패널에서 한 번 재시도, 완료 처리, 중지 중 하나를 선택하세요."
    )
    assert review_repair_table_columns(lang="ko") == ("작업 패키지", "보정 상태")
    assert review_repair_rows(snapshot, lang="ko") == (
        (
            "WP-002",
            "duplicate_required_changes; 시도=2/3; 리뷰=변경 요청",
        ),
    )

    body = review_repair_details_markdown(snapshot, lang="ko")

    assert "리뷰 보정 루프 가드가 다음 작업 패키지를 일시 중지했습니다" in body
    assert "WP-002" in body
    assert "duplicate_required_changes" in body
    assert "최근 보정 메모" in body


def test_review_repair_local_command_snapshot_uses_repair_presenter() -> None:
    snapshot = _review_repair_blocked_snapshot()

    result = review_repair_local_command_snapshot("/review", snapshot, lang="ko")

    assert result.command == "/review"
    assert result.title == "리뷰 보정"
    assert result.severity == "warning"
    assert "리뷰 보정 루프 가드" in result.body
    assert result.action_hint == (
        "중앙 패널에서 한 번 재시도, 완료 처리, 중지 중 하나를 선택하세요."
    )
    assert result.table_columns == ("작업 패키지", "보정 상태")
    assert result.table_rows == (
        (
            "WP-002",
            "duplicate_required_changes; 시도=2/3; 리뷰=변경 요청",
        ),
    )


def test_review_repair_blocked_ids_include_recovery_retry_candidates() -> None:
    snapshot = WorkflowNexusSnapshot(
        execution_recovery=ExecutionRecoverySnapshot(
            state="repair_blocked",
            retry_candidates=("WP-003", "WP-004"),
        )
    )

    assert review_repair_blocked_ids(snapshot) == (
        "WP-003",
        "WP-004",
    )


def test_review_repair_details_include_recovery_only_candidates() -> None:
    snapshot = WorkflowNexusSnapshot(
        execution_recovery=ExecutionRecoverySnapshot(
            state="repair_blocked",
            retry_candidates=("WP-003",),
        )
    )

    assert review_repair_rows(snapshot) == (
        (
            "WP-003",
            "repair_blocked; attempts=(unknown); review=(recovery)",
        ),
    )

    body = review_repair_details_markdown(snapshot)

    assert "WP-003" in body
    assert "repair_blocked" in body


def test_review_repair_details_include_korean_recovery_only_candidates() -> None:
    snapshot = WorkflowNexusSnapshot(
        execution_recovery=ExecutionRecoverySnapshot(
            state="repair_blocked",
            retry_candidates=("WP-003",),
        )
    )

    assert review_repair_rows(snapshot, lang="ko") == (
        (
            "WP-003",
            "복구 차단; 시도=(알 수 없음); 리뷰=(복구)",
        ),
    )

    body = review_repair_details_markdown(snapshot, lang="ko")

    assert "WP-003" in body
    assert "복구 차단" in body


@pytest.mark.asyncio
async def test_nexus_repair_open_review_records_local_command(tmp_path) -> None:
    controller = FakeWorkflowController(_review_repair_blocked_snapshot())
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._handle_review_repair_action("repair-open-review", controller.snapshot())
        await pilot.pause()

        assert app.active_snapshot is not None
        result = _local_command(app.active_snapshot, "/review")
        assert result.title == "리뷰 보정"
        assert result.severity == "warning"
        assert result.action_hint == (
            "중앙 패널에서 한 번 재시도, 완료 처리, 중지 중 하나를 선택하세요."
        )
        assert result.table_columns == ("작업 패키지", "보정 상태")
        assert result.table_rows == (
            (
                "WP-002",
                "duplicate_required_changes; 시도=2/3; 리뷰=변경 요청",
            ),
        )
        assert "duplicate_required_changes" in result.body


@pytest.mark.asyncio
async def test_nexus_repair_retry_uses_custom_execute_retry(tmp_path) -> None:
    controller = FakeWorkflowController(_review_repair_blocked_snapshot())
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._handle_review_repair_action("repair-retry-once", controller.snapshot())
        await pilot.pause()

        assert controller.repair_actions == ["retry"]
        assert controller.retry_confirms == [("custom", ["WP-002"])]
        assert app.current_route == "execution"


@pytest.mark.asyncio
async def test_nexus_repair_retry_workspace_picker_preserves_recovery_candidates(
    tmp_path,
) -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-repair",
        state="needs_user_decision",
        execution_recovery=ExecutionRecoverySnapshot(
            state="repair_blocked",
            retry_candidates=("WP-002",),
        ),
    )
    controller = FakeWorkflowController(snapshot)
    controller.retry_outcome = TextualWorkflowOutcome(
        snapshot,
        message="Choose a target workspace before retrying execution.",
        target_workspace_required=True,
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._handle_review_repair_action("repair-retry-once", controller.snapshot())
        await pilot.pause()

        assert app._pending_execute_retry is not None
        assert app._pending_execute_retry.selector == "custom"
        assert app._pending_execute_retry.package_ids == ("WP-002",)
        assert isinstance(app.screen, WorkspacePicker)


@pytest.mark.asyncio
async def test_poll_workflow_opens_workspace_picker_when_repair_needs_target(
    tmp_path,
) -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-repair",
        state="blueprint_ready",
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Client",
                owner_agent="codex",
                status="pending",
                retryable=True,
            )
        ],
    )
    controller = FakeWorkflowController(snapshot)
    controller.drain_outcome = TextualWorkflowOutcome(
        snapshot,
        message="Choose a target workspace before restarting repairs.",
        target_workspace_required=True,
    )
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._poll_workflow_controller()
        await pilot.pause()

        assert isinstance(app.screen, WorkspacePicker)
        assert app.active_snapshot is not None
        assert app.active_snapshot.session_id == "wf-repair"


@pytest.mark.asyncio
async def test_nexus_repair_retry_button_routes_through_screen_event(tmp_path) -> None:
    controller = FakeWorkflowController(_review_repair_blocked_snapshot())
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)
        screen.apply_snapshot(controller.snapshot())
        await pilot.pause()

        central = screen.query_one(CentralAgentView)
        buttons = list(central.query("#central-actions Button"))
        retry_button = next(
            button for button in buttons if str(button.label) == "한 번 더 재시도"
        )
        retry_button.press()
        await pilot.pause()

        assert controller.repair_actions == ["retry"]
        assert controller.retry_confirms == [("custom", ["WP-002"])]
        assert app.current_route == "execution"


@pytest.mark.asyncio
async def test_nexus_repair_mark_done_and_stop_delegate_to_controller(tmp_path) -> None:
    controller = FakeWorkflowController(_review_repair_blocked_snapshot())
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko"),
        controller,
    )

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        app._handle_review_repair_action("repair-mark-done", controller.snapshot())
        await pilot.pause()
        assert controller.repair_actions == ["accept"]
        assert app.active_snapshot is not None
        assert app.active_snapshot.state == "reviewing"

        app._handle_review_repair_action("repair-stop", controller.snapshot())
        await pilot.pause()
        assert controller.repair_actions == ["accept", "stop"]
        assert app.active_snapshot is not None
        assert app.active_snapshot.state == "failed"
