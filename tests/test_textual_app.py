from __future__ import annotations

from dataclasses import replace
import time
from pathlib import Path

import pytest
from textual import events
from textual.containers import VerticalScroll
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Markdown,
    OptionList,
    RichLog,
    Static,
    TabbedContent,
    TextArea,
)

from trinity.config import TrinityConfig
from trinity.context.shared import SharedContextEngine
from trinity.models import Provider
from trinity.providers.model_discovery import ProviderModelChoice
from trinity.slash_commands import COMMAND_SPECS, SESSION_ONLY_SETTING_NOTICE
from trinity.textual_app import app as textual_app_module
from trinity.textual_app.app import TrinityTextualApp
from trinity.textual_app.presenters import (
    decisions_action_hint,
    decisions_markdown,
    decisions_rows,
    decisions_table_columns,
    history_action_hint,
    history_markdown,
    history_rows,
    history_table_columns,
    improve_action_hint,
    improve_rows,
    improve_table_columns,
    packages_action_hint,
    packages_markdown,
    packages_rows,
    packages_table_columns,
    questions_action_hint,
    questions_markdown,
    questions_rows,
    questions_select_markdown,
    questions_table_columns,
    review_action_hint,
    review_repair_blocked_ids,
    review_repair_details_markdown,
    review_repair_rows,
    review_rows,
    review_table_columns,
    snapshot_context_markdown,
    snapshot_status_markdown,
    snapshot_status_rows,
    snapshot_workflow_markdown,
    snapshot_workflow_rows,
    status_table_columns,
    subtasks_action_hint,
    subtasks_markdown,
    subtasks_rows,
    subtasks_table_columns,
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
from trinity.textual_app.screens.report import ReportScreen
from trinity.textual_app.screens.settings import SettingsScreen
from trinity.textual_app.screens.start import SacredGeometryAnimation, StartScreen
from trinity.textual_app.slash_palette import SlashCommandPaletteProvider
from trinity.textual_app.settings import UISettingsStore
from trinity.textual_app.snapshot import (
    AgentQualitySnapshot,
    PostReviewActionSnapshot,
    LocalCommandSnapshot,
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
from trinity.textual_app.widgets.execution_retry_modal import ExecutionRetryModal, _retry_note
from trinity.textual_app.widgets.inspector import WorkflowInspector
from trinity.textual_app.widgets.local_command_modal import LocalCommandModal
from trinity.textual_app.widgets.model_settings_modal import ModelSettingsModal
from trinity.textual_app.widgets.provider_inspector import ProviderInspector
from trinity.textual_app.widgets.provider_panel import ProviderPanel
from trinity.textual_app.widgets.question_panel import QuestionPanel
from trinity.textual_app.widgets.resume_picker import ResumeWorkflowPicker
from trinity.textual_app.widgets.status_modal import StatusCommandModal
from trinity.textual_app.widgets.target_workspace_confirm_modal import (
    TargetWorkspaceConfirmModal,
)
from trinity.textual_app.widgets.work_package_detail_modal import WorkPackageDetailModal
from trinity.textual_app.widgets.workspace_picker import WorkspacePicker, build_preflight
from trinity.workflow import (
    WorkPackage,
    WorkflowPersistence,
    WorkflowSession,
    WorkflowState,
    WorkStatus,
)


class FakeWorkflowController:
    def __init__(self, snapshot: WorkflowNexusSnapshot | None = None) -> None:
        self.current_snapshot = snapshot or WorkflowNexusSnapshot()
        self.started_prompts: list[str] = []
        self.started_targets: list[tuple[str, ...]] = []
        self.started_models: list[dict[str, str]] = []
        self.follow_ups: list[str] = []
        self.follow_up_targets: list[tuple[str, ...]] = []
        self.follow_up_models: list[dict[str, str]] = []
        self.answers: list[tuple[str, str, bool]] = []
        self.option_answers: list[tuple[str, str, bool]] = []
        self.resumes: list[str] = []
        self.resume_options: list[TextualWorkflowArchiveOption] = []
        self.execution_outcome: TextualWorkflowOutcome | None = None
        self.execution_requests = 0
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
        self.current_snapshot = WorkflowNexusSnapshot(
            session_id="wf-fake",
            goal=self.current_snapshot.goal,
            state="deliberating",
            work_packages=[f"follow-up: {text}"],
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
        self.current_snapshot = WorkflowNexusSnapshot(
            session_id="wf-fake",
            goal=self.current_snapshot.goal,
            state="deliberating",
            decisions=[f"option {option_index}"],
        )
        return TextualWorkflowOutcome(self.current_snapshot)

    def request_execution(self, instruction: str = "") -> TextualWorkflowOutcome:
        self.execution_requests += 1
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
    assert _retry_note(disabled) == "already done"


def test_textual_app_localizes_command_palette_bindings_in_korean(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path, lang="ko"))

    assert _binding_description(app._bindings, "ctrl+q", "quit") == "종료"
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

    text = StatusCommandModal(result)._status_table_text()

    assert "Item" in text
    assert "Value" in text
    assert "Workflow" in text


def test_status_modal_uses_korean_chrome_labels() -> None:
    result = LocalCommandSnapshot(command="/status", title="Status", body="status")
    modal = StatusCommandModal(result, lang="ko")

    assert modal._label("title") == "상태"
    assert modal._label("body").startswith("현재 로컬 상태")
    assert modal._label("close") == "닫기"
    assert modal._status_table_text() == "(상태 행 없음)"


def test_context_modal_uses_korean_chrome_labels() -> None:
    result = LocalCommandSnapshot(command="/context", title="Context", body="context")
    modal = ContextCommandModal(result, lang="ko")

    assert modal._label("title") == "현재 세션 컨텍스트"
    assert modal._label("close") == "닫기"


def test_local_command_modal_uses_korean_close_label() -> None:
    result = LocalCommandSnapshot(command="/workflow", title="Workflow", body="body")
    modal = LocalCommandModal(result, lang="ko")

    assert modal._label("close") == "닫기"


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

    assert status_table_columns(lang="ko") == ("항목", "값")
    assert "- 워크플로우: `wf-ko`" in markdown
    assert "| 프로바이더 | 활성화 | 상태 | 준비 상태 |" in markdown
    assert "| claude | 예 | Queued | 미확인 |" in markdown
    assert "### 실행 복구" in markdown
    assert "실행: `interrupted`" in markdown
    assert ("워크플로우", "wf-ko") in rows
    assert ("프로바이더: claude", "Queued; 활성화=예; 준비 상태=미확인") in rows
    assert ("재시도 후보", "WP-001, WP-003") in rows


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
    assert "- 상태: `blueprint_ready`" in markdown
    assert "### 종합" in markdown
    assert "### 질문" in markdown
    assert "  - 답변: 네" in markdown
    assert "### 결정" in markdown
    assert "### 작업 패키지" in markdown
    assert "### 워크플로우 이력" in markdown
    assert "### 실행 결과" in markdown


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

    assert "- 상태: `blueprint_ready`" in markdown
    assert "- 목표: 워크플로우 확인" in markdown
    assert "- 대기 중 질문: `1`" in markdown
    assert "- 결정: `1`" in markdown
    assert "- 작업 패키지: `1`" in markdown
    assert "- 하위 작업: `1`" in markdown
    assert "- 로컬 정책 복구: `1`" in markdown
    assert "- 실행 로그 항목: `1`" in markdown
    assert "### 실행 복구" in markdown
    assert "재시도 후보: `WP-001`" in markdown
    assert ("상태", "blueprint_ready") in rows
    assert ("대기 중 질문", "1") in rows
    assert ("실행 ID", "exec-run-test") in rows


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
    assert "질문 패널 버튼을 사용하거나" in markdown
    assert "선택된 질문: **q1**" in select_markdown
    assert "질문 패널의 선택지 버튼" in select_markdown
    assert rows[0] == ("q1", "answered", "테마를 선택할까요?", "dark, light")
    assert rows[1] == ("q2", "open", "추가 요청이 있나요?", "(자유 입력)")
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
    assert packages_action_hint(has_packages=False, lang="ko").startswith("blueprint")
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
            )
        ]
    )

    assert subtasks_markdown(empty, lang="ko") == (
        "현재 세션에 기록된 프로바이더 위임 하위 작업이 없습니다."
    )
    assert "1. **ST-001** [done] WP-001 -> codex: 완료" in subtasks_markdown(
        snapshot,
        lang="ko",
    )
    assert subtasks_rows(snapshot, lang="ko") == (
        ("ST-001", "WP-001", "codex", "done", "완료"),
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
        ("상태", "reviewing"),
        ("라운드", "2"),
        ("목표", "이력 확인"),
        ("로컬 명령", "/status - Status"),
        ("실행", "WP-001 codex: done"),
    )
    assert "- 워크플로우: `wf-ko`" in markdown
    assert "- 상태: `reviewing`" in markdown
    assert "### 최근 실행 로그" in markdown
    assert "### 최근 로컬 항목" in markdown
    assert "- **로컬 명령**: /status - Status" in markdown
    assert history_table_columns(lang="ko") == ("종류", "항목")
    assert history_action_hint(has_history=False, lang="ko").startswith("프롬프트 실행")
    assert history_action_hint(has_history=True, lang="ko") == ""


def test_history_empty_presenter_uses_korean_labels() -> None:
    assert history_markdown(WorkflowNexusSnapshot(), (), lang="ko") == (
        "현재 Textual 세션에 기록된 로컬 이력이 없습니다."
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
        ("상태", "reviewing"),
        ("작업 패키지", "2"),
        ("대기 중 WP 리뷰", "WP-001"),
        ("리뷰된 WP", "WP-002:approved"),
        ("최종 리뷰", "approved / 리뷰어 codex"),
    )
    assert review_table_columns(lang="ko") == ("항목", "값")
    assert review_action_hint(lang="ko").startswith("`/review wp`")


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
        ("상태", "post_review_ready"),
        ("보충 라운드", "1"),
        ("조치 항목", "(none)"),
    )
    assert improve_rows(snapshot, lang="ko") == (
        ("워크플로우", "wf-improve"),
        ("상태", "post_review_ready"),
        ("보충 라운드", "2"),
        ("AI-001", "pending; severity=high; kind=test; title=Fix tests"),
    )
    assert improve_table_columns(lang="ko") == ("항목", "값")
    assert improve_action_hint(lang="ko").startswith("`/improve high`")


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

    monkeypatch.setattr("trinity.textual_app.app.discover_provider_models", fake_discover)
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
        assert str(geometry.render()).strip()


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
        assert start_selector.selected_agents() == ("claude", "codex")
        claude_toggle = start_selector.query_one("#recipient-claude", AgentToggle)
        codex_toggle = start_selector.query_one("#recipient-codex", AgentToggle)
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
        labels = app.screen._choice_labels("codex")
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
        assert "gpt-5.5" not in app.screen._choice_labels("codex")

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

        assert "gpt-5.5  cli-live" in app.screen._choice_labels("codex")


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
async def test_textual_export_snapshot_uses_korean_markdown_labels(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    app = TrinityTextualApp(config)
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
async def test_textual_export_empty_snapshot_does_not_create_report(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(100, 30)):
        app._export_report_markdown(WorkflowNexusSnapshot())

    report_dir = app.config.effective_state_dir / "reports"
    assert not list(report_dir.glob("report-*.md"))


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
    assert "컨텍스트 1,000 (runtime)" in md
    assert "세션 session\\-1234" in md
    assert "프로필 implementer" in md
    assert "모드 execute, review" in md
    assert "출력 execution\\_v1" in md
    assert "강점 implementation, testing, repair, \\+1" in md
    assert "## 자문 에이전트 품질" in md
    assert "점수 0\\.667; 성공 2/3; 차단 1; 변경 요청 4" in md
    assert "## 합의" in md
    assert "**진행**: 진행중" in md
    assert "## WP 라우팅" in md
    assert "상태: done; 담당 codex; 실행자 codex; 레인 직렬" in md
    assert "라우팅: 종류 implementation; 프로필 default\\-v1; 점수 0\\.95" in md
    assert (
        "리뷰: peer 없음; 리뷰어 \\(none\\); 이유 only codex is active; "
        "no non\\-owner peer reviewer is available"
    ) in md
    assert "## 실행 로그" in md
    assert "## 실행 복구" in md
    assert "## 미해결 질문" in md


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

    markdown = view._markdown()

    assert "- `승인` by `codex`" in markdown
    assert "- **AI-001** [high][대기] Add smoke test" in markdown
    assert "- **AI-002** [low][완료] Update docs" in markdown
    assert "`approved`" not in markdown
    assert "[pending]" not in markdown


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

    markdown = view._markdown()

    assert "- `approved` by `codex`" in markdown
    assert "- **AI-001** [high][pending] Add smoke test" in markdown


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

    assert view._execution_progress(snapshot) == (
        "실행 중: 1 완료 / 1 실행중 / 1 대기 / 1 막힘"
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

    assert view._execution_progress(snapshot) == (
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
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

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

        app.action_go_execution()
        await pilot.pause()

        execution = app.screen
        assert isinstance(execution, ExecutionMatrixScreen)
        assert str(launch_cwd.resolve()) in str(
            execution.query_one("#execution-header").content
        )


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
        assert app.current_route == "nexus"
        assert isinstance(app.screen, NexusScreen)


@pytest.mark.asyncio
async def test_start_submission_persists_selected_workspace_target(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)
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
        assert "readiness=not checked" in table_text


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
        assert app.active_snapshot.local_commands[-1].table_columns == ("항목", "값")
        assert ("상태", "idle") in app.active_snapshot.local_commands[-1].table_rows
        table_text = str(app.screen.query_one("#status-command-table", Static).render())
        assert "워크플로우" in table_text


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
        assert "Command Result" in central._markdown()
        assert "**/workflow - Workflow**" in central._markdown()


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
        assert [str(button.label) for button in buttons] == ["실패 WP 재시도"]

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

    assert [package.id for package in modal._display_packages()] == ["WP-001", "WP-003"]
    assert modal._ids_for_selector("all") == ("WP-001", "WP-003")
    modal.selector = "failed"
    assert [package.id for package in modal._display_packages()] == ["WP-001"]


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

    assert [package.id for package in modal._display_packages()] == [
        "WP-010",
        "WP-050",
        "WP-075",
    ]
    assert modal._ids_for_selector("all") == ("WP-010", "WP-050", "WP-075")
    modal.selector = "blocked"
    assert [package.id for package in modal._display_packages()] == ["WP-050"]


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

    assert [package.id for package in modal._display_packages()] == ["WP-001", "WP-003"]
    assert modal._selected_package_ids() == ("WP-003",)


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

    assert modal._label("title") == "실행 재시도"
    assert modal._filter_label("failed") == "실패"
    assert modal._summary_text() == "복구: failed  대상: /workspace/game"
    assert modal._header_text().startswith("WP      상태")
    assert modal._selected_text() == "선택됨: WP-001"


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

    assert statuses == ["실패", "차단", "실행중"]


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

    assert modal._label("title") == "Execute Retry"
    assert modal._filter_label("failed") == "Failed"
    assert modal._summary_text() == "Recovery: none  Target: (not selected)"
    assert modal._header_text().startswith("WP      Status")
    assert modal._selected_text() == "Selected: WP-001"


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
        assert result.title == "Workflow"
        assert result.table_columns == ("항목", "값")
        assert ("상태", "blueprint_ready") in result.table_rows
        assert "- 상태: `blueprint_ready`" in result.body
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
        assert result.table_columns == ("ID", "상태", "질문", "선택지")
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
        assert result.action_hint.startswith("blueprint")


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
        assert result.table_columns == ("ID", "작업 패키지", "위임 대상", "상태", "요약")
        assert result.table_rows[0] == ("ST-001", "WP-001", "codex", "done", "Done")
        assert "1. **ST-001** [done] WP-001 -> codex: Done" in result.body
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
        assert "Command Result" in central._markdown()
        assert "**/not-a-command - Unknown Command**" in central._markdown()


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
        assert "Use `/target <path>`" in central._markdown()
        assert controller.started_prompts == []
        assert controller.follow_ups == []


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
        assert result.body == "현재 Textual 세션에 기록된 로컬 이력이 없습니다."
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
        assert result.title == "Review"
        assert result.table_columns == ("항목", "값")
        assert ("워크플로우", "wf-review") in result.table_rows
        assert ("대기 중 WP 리뷰", "WP-001") in result.table_rows
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
        assert result.title == "Improve"
        assert result.table_columns == ("항목", "값")
        assert ("워크플로우", "wf-improve") in result.table_rows
        assert ("보충 라운드", "1") in result.table_rows
        assert (
            "AI-001",
            "pending; severity=high; kind=test; title=Fix tests",
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
        assert _binding_description(start._bindings, "ctrl+enter", "submit") == "계획"

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

        for _ in range(COMMAND_LIMIT + 2):
            await pilot.press("down")
        await pilot.pause()

        selected = [str(option.content) for option in composer.query(".command-option-selected")]
        visible = [str(option.content) for option in composer.query(".command-option")]

        assert any("/workflow" in option for option in selected)
        assert any("/workflow" in option for option in visible)


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
        ("WP 재분배", "WP의 범위"),
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
        assert "Command Result" in central._markdown()
        assert "Local Command Results" not in central._markdown()


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
        assert "round 1 synthesizing" in central._markdown()


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
        assert "duplicate_required_changes" in app.screen._markdown()


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
            "DONE",
            "ISSUE",
            "IDLE",
            "?",
        ]


def test_execution_matrix_compacts_reviewer_status_labels() -> None:
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
        == "peer 없음"
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
        == "2차필요"
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

        assert "리뷰: peer 없음" in row_text


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
    assert _detail_button_label(package, lang="ko") == "2차리뷰"
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

        activity_lines = screen._activity_lines()
        assert activity_lines[0] == "Activity"
        assert "... 4 earlier log lines hidden" in activity_lines
        assert "event-11" in activity_lines


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
            assert "실행중 1" in summary
            assert "리뷰 0" in summary
            assert "대기 0" in summary
            assert "완료 0" in summary
            assert "문제 1" in summary
            assert "레인 1" in summary
            assert "직렬 1" in summary
            assert "재시도 1" in summary
            assert "워크플로우 running" in summary
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
            assert "리스크: medium g1" in _widget_tree_text(rows[0])
            assert "리스크: high serial" in _widget_tree_text(rows[1])

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

            activity_lines = screen._activity_lines()
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
        markdown = app.screen._markdown()
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
        recent_lines = screen._activity_lines()
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
        assert screen._activity_lines() == recent_lines


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
                        status="failed",
                        retryable=True,
                        review_status="queued",
                        reviewer_agent="antigravity",
                        risk="medium",
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
        assert "리스크/레인" in header_text

        row_text = _widget_tree_text(
            screen.query("#execution-package-list .execution-package-row").first()
        )
        assert "리뷰: agy 대기" in row_text
        assert "리스크: medium" in row_text
        assert "상세" in row_text

        activity_lines = screen._activity_lines()
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

    assert modal._render_lines() == lines


def test_execution_log_modal_windows_large_logs() -> None:
    lines = [f"event-{index}" for index in range(1, MAX_RENDERED_LOG_LINES + 26)]
    modal = ExecutionLogModal(lines)
    rendered = modal._render_lines()

    assert rendered[0] == "... 25 earlier log lines hidden"
    assert rendered[1] == "event-26"
    assert rendered[-1] == f"event-{MAX_RENDERED_LOG_LINES + 25}"
    assert "event-1" not in rendered
    assert len(rendered) == MAX_RENDERED_LOG_LINES + 1


def test_execution_log_modal_reports_visible_line_count() -> None:
    short = ExecutionLogModal(["event-1", "event-2"])
    large = ExecutionLogModal(
        [f"event-{index}" for index in range(1, MAX_RENDERED_LOG_LINES + 26)]
    )
    korean = ExecutionLogModal(["event-1", "event-2"], lang="ko")

    assert short._status_text() == "Showing 2 of 2 lines"
    assert large._status_text() == (
        f"Showing {MAX_RENDERED_LOG_LINES} of {MAX_RENDERED_LOG_LINES + 25} lines"
    )
    assert korean._status_text() == "2/2줄 표시"


def test_execution_log_modal_filters_lines_case_insensitively() -> None:
    modal = ExecutionLogModal(
        [
            "WP-001 started by codex",
            "WP-002 failed with provider error",
            "WP-003 review completed",
            "wp-004 FAILED after retry",
        ]
    )

    assert modal._render_lines("FAILED") == [
        "WP-002 failed with provider error",
        "wp-004 FAILED after retry",
    ]
    assert modal._render_lines("review") == ["WP-003 review completed"]
    assert modal._status_text("FAILED") == "Showing 2 of 2 matches"


def test_execution_log_modal_filters_large_match_sets() -> None:
    lines = [f"WP-{index:03d} failed" for index in range(1, MAX_RENDERED_LOG_LINES + 4)]
    modal = ExecutionLogModal(lines)
    rendered = modal._render_lines("failed")

    assert rendered[0] == "... 3 earlier log lines hidden"
    assert rendered[1] == "WP-004 failed"
    assert rendered[-1] == f"WP-{MAX_RENDERED_LOG_LINES + 3:03d} failed"
    assert modal._status_text("failed") == (
        f"Showing {MAX_RENDERED_LOG_LINES} of {MAX_RENDERED_LOG_LINES + 3} matches"
    )


def test_execution_log_modal_shows_empty_filtered_state() -> None:
    modal = ExecutionLogModal(["WP-001 started"])
    korean = ExecutionLogModal(["WP-001 started"], lang="ko")

    assert modal._render_lines("missing") == ["No matching execution log lines."]
    assert korean._render_lines("missing") == ["일치하는 실행 로그가 없습니다."]
    assert modal._status_text("missing") == "0 matches"
    assert korean._status_text("missing") == "0개 결과"


def test_execution_log_modal_localizes_large_log_window() -> None:
    lines = [f"event-{index}" for index in range(1, MAX_RENDERED_LOG_LINES + 3)]
    modal = ExecutionLogModal(lines, lang="ko")

    assert modal._render_lines()[0] == "... 이전 로그 2줄 숨김"


def test_execution_log_modal_keeps_empty_state() -> None:
    assert ExecutionLogModal([])._render_lines() == ["No execution log yet."]
    assert ExecutionLogModal([], lang="ko")._render_lines() == [
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
    markdown = modal._markdown()

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

    markdown = modal._markdown()

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

    markdown = modal._markdown()

    assert "- Retry unavailable: already done" in markdown
    assert "- Retry candidate: `WP-002`" not in markdown


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

    markdown = modal._markdown()

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

    markdown = modal._markdown()

    assert "- Peer review was skipped; treat confidence as lower." in markdown


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

    markdown = modal._markdown()

    assert (
        "- 리뷰 생략 사유: only codex is active; "
        "no non-owner peer reviewer is available"
    ) in markdown
    assert "## 리뷰 계획" in markdown


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

    markdown = modal._markdown()

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
        ),
        lang="ko",
    )

    markdown = modal._markdown()

    assert "- 상태: `실패`" in markdown
    assert "- 리뷰: `변경 요청`" in markdown
    assert "## 리뷰 계획\n- 상태: `변경 요청`" in markdown
    assert "## 리뷰\n- 리뷰어: `-`\n- 상태: `변경 요청`" in markdown
    assert "- 리뷰가 완료 전 1개 변경을 요청했습니다." in markdown
    assert "`changes_requested`" not in markdown


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

    markdown = modal._markdown()

    assert "- 상태: `완료`" in markdown
    assert "- 리뷰: `2차 리뷰 필요`" in markdown
    assert "## 리뷰 계획\n- 상태: `2차 리뷰 필요`" in markdown
    assert "- 2차 리뷰가 대기 중입니다." in markdown
    assert "`needs_second_review`" not in markdown


def test_work_package_detail_modal_preserves_unknown_status_values() -> None:
    modal = WorkPackageDetailModal(
        WorkPackageSnapshot(
            id="WP-013",
            title="Unknown status",
            owner_agent="codex",
            status="waiting_for_external_input",
        ),
        lang="ko",
    )

    assert "- 상태: `waiting_for_external_input`" in modal._markdown()


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
        markdown = app.screen._markdown()
        assert "## 요약" in markdown
        assert "- 제목: Client" in markdown
        assert "- 상태: `실패`" in markdown
        assert "- 리뷰: `변경 요청`" in markdown
        assert "- 소유자: `codex`" in markdown
        assert "- 실행 필요: `예`" in markdown
        assert "## 액션 컨텍스트" in markdown
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

    title_text = modal._title_text()
    markdown = modal._markdown()

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

    assert "- Execution lane: `serial`" in modal._markdown()


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

    assert "- 실행 레인: `직렬`" in serial._markdown()
    assert "- 실행 레인: `미지정`" in unspecified._markdown()
    assert "- 실행 레인: `g3`" in grouped._markdown()


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
    assert "상태: Ready" in meta
    assert "준비 상태: ready" in meta
    assert "미션: Implementation and testing" in meta
    assert "모드: execute, review" in meta
    assert "강점: implementation 0.95" in meta
    assert "컨텍스트 프로필: implementer" in meta
    assert "출력 계약: execution_v1" in meta
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
        assert "line 29" in app.screen._provider_output(app.screen.providers[0])


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
            )
        )
        await pilot.pause()

        inspector = screen.query_one(WorkflowInspector)
        assert "5 WP · 완료 1 · 실행 1 · 대기 2 · 막힘 1" in str(
            inspector.query_one("#inspector-progress").content
        )
        next_content = str(inspector.query_one("#inspector-next").content)
        assert "WP-005 Codex · Docs · 그룹 2" in next_content
        assert "대기: WP-002" in next_content
        assert "복구 2/2 · missing token" in str(
            inspector.query_one("#inspector-blocked").content
        )
        workflow_content = str(inspector.query_one("#inspector-workflow").content)
        assert "상태: blueprint_ready" in workflow_content
        assert "라운드: 1" in workflow_content


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
        assert app.screen._label("all") == "전체"
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
async def test_start_select_workspace_opens_workspace_picker(tmp_path) -> None:
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path),
        FakeWorkflowController(),
        launch_cwd=tmp_path,
    )

    async with app.run_test(size=(140, 44)) as pilot:
        await pilot.click("#choose-workspace")
        await pilot.pause()

        assert isinstance(app.screen, WorkspacePicker)
        picker = app.screen
        assert picker.intent == "select"
        assert str(picker.query_one("#workspace-picker-title", Static).content) == (
            "Select Workspace"
        )
        assert str(picker.query_one("#confirm-execute", Button).label) == "Use Workspace"


@pytest.mark.asyncio
async def test_start_select_workspace_updates_workspace_candidate(tmp_path) -> None:
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path),
        FakeWorkflowController(),
        launch_cwd=tmp_path,
    )

    async with app.run_test(size=(140, 44)) as pilot:
        await pilot.click("#choose-workspace")
        await pilot.pause()
        picker = app.screen
        assert isinstance(picker, WorkspacePicker)

        picker.action_confirm()
        await pilot.pause()

        start = app.get_screen("start", StartScreen)
        assert app.workspace_candidate == tmp_path
        assert str(tmp_path) in str(start.query_one("#workspace-candidate").content)


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
        await pilot.click("#choose-workspace")
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
async def test_nexus_select_workspace_cta_selects_target_without_execution(
    tmp_path,
) -> None:
    control_repo = tmp_path / "control"
    target = tmp_path / "target-app"
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

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()

        nexus = app.screen
        assert isinstance(nexus, NexusScreen)
        assert str(nexus.query_one("#open-provider-inspector", Button).label) == (
            "Open Provider Inspector"
        )
        assert str(nexus.query_one("#request-execute", Button).label) == "Execute"
        assert str(nexus.query_one("#select-workspace", Button).label) == (
            "Select Workspace"
        )
        assert [child.id for child in nexus.query_one("#nexus-action-bar").children] == [
            "open-provider-inspector",
            "select-workspace",
            "nexus-target-workspace",
            "request-execute",
        ]
        workspace_label = nexus.query_one("#nexus-target-workspace", Static)
        assert str(target.resolve()) in str(workspace_label.content)
        assert workspace_label.styles.height.value == 3
        assert workspace_label.styles.content_align_vertical == "bottom"

        await pilot.click("#select-workspace")
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
        nexus = app.get_screen("nexus", NexusScreen)
        assert str(nexus.query_one("#request-execute", Button).label) == "Execute"
        assert str(nexus.query_one("#select-workspace", Button).label) == (
            "Select Workspace"
        )
        assert str(target.resolve()) in str(
            nexus.query_one("#nexus-target-workspace", Static).content
        )


@pytest.mark.asyncio
async def test_nexus_action_bar_uses_configured_korean_labels(tmp_path) -> None:
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
        assert str(nexus.query_one("#open-provider-inspector", Button).label) == (
            "프로바이더 인스펙터"
        )
        assert str(nexus.query_one("#request-execute", Button).label) == "실행"
        assert str(nexus.query_one("#select-workspace", Button).label) == (
            "작업 폴더 선택"
        )
        workspace_label = str(
            nexus.query_one("#nexus-target-workspace", Static).content
        )
        assert workspace_label.startswith("작업 폴더: ")
        assert str(target.resolve()) in workspace_label
        assert nexus.query_one("#nexus-composer", PromptComposer).placeholder == (
            "답변하거나 방향을 조정하세요. / 로 명령 입력"
        )

    screen = NexusScreen(
        TrinityConfig.default_config(project_dir=control_repo, lang="ko")
    )
    assert screen._workspace_label() == "작업 폴더: 선택 안됨"


@pytest.mark.asyncio
async def test_nexus_execute_requests_execution_when_target_is_selected(
    tmp_path,
) -> None:
    target = tmp_path / "target-app"
    target.mkdir()
    controller = FakeWorkflowController(
        WorkflowNexusSnapshot(
            session_id="wf-fake",
            state="blueprint_ready",
            target_workspace=str(target),
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
        assert str(nexus.query_one("#request-execute", Button).label) == "Execute"

        await pilot.click("#request-execute")
        await pilot.pause()

        assert controller.execution_requests == 1


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

        screen.query_one("#theme-mode").value = "dark"
        screen.query_one("#density").value = "compact"
        screen.action_apply()
        await pilot.pause()

    saved = UISettingsStore(tmp_path / ".trinity").load()
    assert saved.theme_mode == "dark"
    assert saved.density == "compact"


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
        assert result.title == "Review Repair"
        assert result.severity == "warning"
        assert result.table_columns == ("WP", "Repair state")
        assert result.table_rows == (
            (
                "WP-002",
                "duplicate_required_changes; attempts=2/3; review=changes_requested",
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


def test_nexus_refine_prompts_are_scope_specific(tmp_path) -> None:
    screen = NexusScreen(TrinityConfig.default_config(project_dir=tmp_path, lang="ko"))

    feature_prompt = screen._refine_prompt("refine-features")
    risk_prompt = screen._refine_prompt("refine-risks")
    package_prompt = screen._refine_prompt("refine-work-packages")

    assert "핵심 기능" in feature_prompt
    assert "실행 리스크" in risk_prompt
    assert "WP의 범위" in package_prompt
