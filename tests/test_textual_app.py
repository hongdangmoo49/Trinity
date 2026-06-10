from __future__ import annotations

from pathlib import Path

import pytest
from textual import events
from textual.containers import VerticalScroll
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Markdown,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TextArea,
)

from trinity.config import TrinityConfig
from trinity.context.shared import SharedContextEngine
from trinity.models import Provider
from trinity.providers.model_discovery import ProviderModelChoice
from trinity.slash_commands import SESSION_ONLY_SETTING_NOTICE
from trinity.textual_app.app import TrinityTextualApp
from trinity.textual_app.report_export import (
    snapshot_report_markdown,
    unique_report_path,
)
from trinity.textual_app.screens.execution_matrix import ExecutionMatrixScreen
from trinity.textual_app.screens.nexus import NexusScreen
from trinity.textual_app.screens.report import ReportScreen
from trinity.textual_app.screens.settings import SettingsScreen
from trinity.textual_app.screens.start import SacredGeometryAnimation, StartScreen
from trinity.textual_app.settings import UISettingsStore
from trinity.textual_app.snapshot import (
    LocalCommandSnapshot,
    ProviderSnapshot,
    QuestionSnapshot,
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
    AgentRecipientModelSelector,
)
from trinity.textual_app.widgets.composer import COMMAND_LIMIT, ComposerTextArea, PromptComposer
from trinity.textual_app.widgets.confirm_quit_modal import ConfirmQuitModal
from trinity.textual_app.widgets.context_modal import ContextCommandModal
from trinity.textual_app.widgets.execution_retry_modal import ExecutionRetryModal, _retry_note
from trinity.textual_app.widgets.inspector import WorkflowInspector
from trinity.textual_app.widgets.local_command_modal import LocalCommandModal
from trinity.textual_app.widgets.provider_inspector import ProviderInspector
from trinity.textual_app.widgets.provider_panel import ProviderPanel
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
        return TextualWorkflowOutcome(self.current_snapshot)

    def clear_target_workspace(self) -> TextualWorkflowOutcome:
        self.target_cleared = True
        self.target_workspace = None
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

    markdown = TrinityTextualApp._snapshot_status_markdown(snapshot)
    rows = TrinityTextualApp._snapshot_status_rows(snapshot)

    assert "### Execution Recovery" in markdown
    assert "Execution: `interrupted`" in markdown
    assert ("Execution", "interrupted") in rows
    assert ("Retry candidates", "WP-001, WP-003") in rows


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

    markdown = TrinityTextualApp._snapshot_context_markdown(snapshot)

    assert "### Workflow History" in markdown
    assert "- event-1" in markdown
    assert "- event-12" in markdown
    assert "### Execution Results" in markdown
    assert "WP-001 claude: failed - missing file" in markdown


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
        claude_toggle = start_selector.query_one("#recipient-claude", Checkbox)
        codex_toggle = start_selector.query_one("#recipient-codex", Checkbox)
        codex_model = start_selector.query_one("#recipient-model-codex", Select)
        assert claude_toggle.value is True
        assert claude_toggle.compact is True
        assert codex_toggle.value is True
        assert codex_toggle.compact is True
        assert codex_model.value == "default"
        assert codex_model.compact is True
        assert start_selector.model_option_labels("claude")[0] == "claude(default)"
        assert start_selector.model_option_labels("codex")[0] == "codex(default)"

        app.switch_to("nexus")
        await pilot.pause()

        nexus_selector = app.screen.query_one(
            "#nexus-recipient-selector",
            AgentRecipientModelSelector,
        )
        assert nexus_selector.selected_agents() == ("claude", "codex")
        assert nexus_selector.query_one("#recipient-model-claude", Select).value == "default"


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
            )
        ],
    )

    md = snapshot_report_markdown(snapshot)

    assert "## Providers" in md
    assert "**codex**: gpt\\-5\\.5; context 272,000 (local\\_cli\\_cache)" in md
    assert "session 019ea9e3\\-426" in md


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
async def test_start_unknown_slash_does_not_start_workflow(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

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
        assert "Local Command Results" in central._markdown()
        assert "#### /workflow - Workflow" in central._markdown()


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
        assert "Local Command Results" in central._markdown()
        assert "#### /not-a-command - Unknown Command" in central._markdown()


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
        assert "Use the option buttons in the central panel" in (
            central.snapshot.local_commands[-1].body
        )
        assert central.query_one("#answer-q-1-1")


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

        for _ in range(COMMAND_LIMIT + 1):
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

        central = screen.query_one(CentralAgentView)
        assert central.query_one("#answer-q-1-1")
        assert central.query_one("#answer-q-1-2")


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

        central = screen.query_one(CentralAgentView)
        assert "Questions for you (2)" in str(central.query_one("#central-question-title").content)
        assert central.query_one("#answer-q-1-1")
        assert central.query_one("#answer-q-1-2")
        assert central.query_one("#answer-q-2-1")
        assert central.query_one("#answer-q-2-2")
        rendered_questions = [str(item.content) for item in central.query(".question-text")]
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
        assert "Local Command Results" in central._markdown()


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

        central = screen.query_one(CentralAgentView)
        assert "1. [answered] Engine?" in [
            str(item.content) for item in central.query(".question-text")
        ]
        assert "Answer: Godot" in [str(item.content) for item in central.query(".question-answer")]
        assert not central.query("#answer-q-1-1")
        assert central.query_one("#answer-q-2-1")


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

        central = screen.query_one(CentralAgentView)
        grid = central.query_one(".question-options")
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
        assert isinstance(panel, VerticalScroll)
        assert panel.has_class("provider-running")
        assert "Running" in str(panel.query_one(".provider-status").content)
        assert central.has_class("central-running")
        assert "Central Agent" in str(central.query_one("#central-title").content)
        assert "round 1 synthesizing" in central._markdown()


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
        row_text = " ".join(str(child.render()) for child in rows.first().children)

        assert len(rows) == 1
        assert "Rust contracts" in row_text
        assert "codex" in row_text
        assert "claude fallback" in row_text
        assert "running" in row_text
        assert "high" in row_text
        rows.first().query_one("#wp-detail-0", Button).press()
        await pilot.pause()

        assert isinstance(app.screen, WorkPackageDetailModal)
        assert "WP-001: Rust contracts" in str(
            app.screen.query_one("#work-package-detail-title", Static).content
        )


@pytest.mark.asyncio
async def test_execution_matrix_header_uses_row_column_layout(tmp_path) -> None:
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

        expected_columns = [
            "execution-package-task",
            "execution-package-assignee",
            "execution-package-executor",
            "execution-package-status",
            "execution-package-review",
            "execution-package-risk",
            "execution-package-spec",
        ]
        header = screen.query("#execution-package-list .execution-package-header").first()
        row = screen.query("#execution-package-list .execution-package-row").first()

        assert [_column_class(child, expected_columns) for child in header.children] == (
            expected_columns
        )
        assert [_column_class(child, expected_columns) for child in row.children] == (
            expected_columns
        )
        assert [child.region.x for child in header.children] == [
            child.region.x for child in row.children
        ]

        await pilot.press("f")
        await pilot.pause()

        header = screen.query("#execution-package-list .execution-package-header").first()
        row = screen.query("#execution-package-list .execution-package-row").first()
        assert [child.region.x for child in header.children] == [
            child.region.x for child in row.children
        ]


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
        compact_text = " ".join(str(child.render()) for child in compact_row.children)
        execution_screen = screen.query_one("#execution-screen")
        assert not execution_screen.has_class("execution-task-expanded")
        assert "detailed Korean" not in compact_text

        await pilot.press("f")
        await pilot.pause()

        expanded_row = screen.query("#execution-package-list .execution-package-row").first()
        expanded_text = " ".join(str(child.render()) for child in expanded_row.children)
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
async def test_provider_panel_renders_scrollable_raw_output(tmp_path) -> None:
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
        assert isinstance(panel, VerticalScroll)
        assert "line 29" in str(panel.query_one(".provider-summary").content)


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
                execution_log=["state_changed: blueprint_ready"],
            )
        )
        await pilot.pause()

        inspector = screen.query_one(WorkflowInspector)
        assert "wf-inspector" in str(inspector.query_one("#inspector-workflow").content)
        assert "Use Textual" in str(inspector.query_one("#inspector-decisions").content)


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
async def test_start_choose_now_opens_workspace_picker(tmp_path) -> None:
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path),
        FakeWorkflowController(),
    )

    async with app.run_test(size=(140, 44)) as pilot:
        await pilot.click("#choose-workspace")
        await pilot.pause()

        assert isinstance(app.screen, WorkspacePicker)


@pytest.mark.asyncio
async def test_start_choose_now_updates_workspace_candidate(tmp_path) -> None:
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path),
        FakeWorkflowController(),
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
        app.screen.query_one(CentralAgentView).apply_snapshot(controller.snapshot())
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
        app.screen.query_one(CentralAgentView).apply_snapshot(controller.snapshot())
        button = app.screen.query_one("#answer-q-1-1", Button)
        button.press()
        await pilot.pause()

        assert button.id == "answer-q-1-1"
        assert controller.answers == [("메타플레이", "정적 전용으로 시작한다", False)]


@pytest.mark.asyncio
async def test_workspace_picker_opens_from_nexus_execute(tmp_path) -> None:
    controller = FakeWorkflowController()
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)
        screen.action_request_execute()
        await pilot.pause()

        assert isinstance(app.screen, WorkspacePicker)
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
        assert len(screen.query("#execution-package-list .execution-package-row")) == 1


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


def test_review_repair_details_markdown_summarizes_blocked_packages() -> None:
    snapshot = _review_repair_blocked_snapshot()

    assert TrinityTextualApp._review_repair_blocked_ids(snapshot) == ("WP-002",)
    assert TrinityTextualApp._review_repair_rows(snapshot) == (
        (
            "WP-002",
            "duplicate_required_changes; attempts=2/3; review=changes_requested",
        ),
    )

    body = TrinityTextualApp._review_repair_details_markdown(snapshot)

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

    assert TrinityTextualApp._review_repair_blocked_ids(snapshot) == (
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

    assert TrinityTextualApp._review_repair_rows(snapshot) == (
        (
            "WP-003",
            "repair_blocked; attempts=(unknown); review=(recovery)",
        ),
    )

    body = TrinityTextualApp._review_repair_details_markdown(snapshot)

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
