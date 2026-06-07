from __future__ import annotations

import pytest
from textual import events
from textual.containers import VerticalScroll
from textual.widgets import Button, DataTable, RichLog, TabbedContent, TextArea

from trinity.config import TrinityConfig
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
    SynthesisSnapshot,
    WorkflowNexusSnapshot,
)
from trinity.textual_app.workflow_controller import (
    TextualWorkflowArchiveOption,
    TextualWorkflowOutcome,
)
from trinity.tui.report import DeliberationReportBuilder
from trinity.textual_app.widgets.central_agent import CentralAgentView
from trinity.textual_app.widgets.composer import COMMAND_LIMIT, ComposerTextArea, PromptComposer
from trinity.textual_app.widgets.inspector import WorkflowInspector
from trinity.textual_app.widgets.provider_inspector import ProviderInspector
from trinity.textual_app.widgets.provider_panel import ProviderPanel
from trinity.textual_app.widgets.resume_picker import ResumeWorkflowPicker
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
        self.follow_ups: list[str] = []
        self.answers: list[tuple[str, str, bool]] = []
        self.option_answers: list[tuple[str, str, bool]] = []
        self.resumes: list[str] = []
        self.resume_options: list[TextualWorkflowArchiveOption] = []
        self.execution_requests = 0
        self.target_workspace = None
        self.target_cleared = False

    def snapshot(self) -> WorkflowNexusSnapshot:
        return self.current_snapshot

    def start_prompt(self, prompt: str) -> TextualWorkflowOutcome:
        self.started_prompts.append(prompt)
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

    def submit_follow_up(self, text: str) -> TextualWorkflowOutcome:
        self.follow_ups.append(text)
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
        return TextualWorkflowOutcome(
            self.current_snapshot,
            target_workspace_required=True,
        )

    def set_target_workspace(self, path, *, control_repo_confirmed: bool = False):
        self.target_workspace = path
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
        return None


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


def test_textual_app_localizes_command_palette_bindings_in_korean(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path, lang="ko"))

    assert _binding_description(app._bindings, "ctrl+q", "quit") == "종료"
    assert _binding_description(app._bindings, "ctrl+p", "command_palette") == "팔레트"
    assert _binding_tooltip(app._bindings, "ctrl+p", "command_palette") == "명령 팔레트 열기"


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
    controller = FakeWorkflowController()
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), controller)

    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, StartScreen)

        composer = screen.query_one(PromptComposer)
        composer.set_text("/status ")
        composer.action_submit()
        await pilot.pause()

        assert app.current_route == "start"
        assert isinstance(app.screen, StartScreen)
        assert controller.started_prompts == []
        assert controller.follow_ups == []
        assert composer.text == ""
        assert app.active_snapshot is not None
        assert app.active_snapshot.local_commands[-1].command == "/status"
        assert app.active_snapshot.local_commands[-1].title == "Status"
        assert app.active_snapshot.local_commands[-1].table_columns == ("Item", "Value")
        assert ("State", "idle") in app.active_snapshot.local_commands[-1].table_rows


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
        assert "`/workflow`" in central._markdown()


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
        assert "`/not-a-command`" in central._markdown()


@pytest.mark.asyncio
async def test_textual_session_setting_commands_are_local_session_only_results(
    tmp_path,
) -> None:
    controller = FakeWorkflowController()
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
        assert isinstance(app.screen, ResumeWorkflowPicker)
        button = app.screen.query_one("#resume-archive-1", Button)
        button.press()
        await pilot.pause()

        assert controller.resumes == ["1"]
        assert app.active_snapshot is not None
        assert app.active_snapshot.session_id == "wf-resumed-1"


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
        filtered_options = [
            str(option.content) for option in composer.query(".command-option")
        ]

        assert any("/execute" in option for option in filtered_options)

        composer.set_text("/rep")
        await pilot.pause()
        report_options = [
            str(option.content) for option in composer.query(".command-option")
        ]

        assert any("/report" in option for option in report_options)

        composer.set_text("/q")
        await pilot.pause()
        quit_options = [
            str(option.content) for option in composer.query(".command-option")
        ]

        assert any("/q" in option for option in quit_options)
        assert any("/quit" in option for option in quit_options)

        composer.set_text("hello /status")
        await pilot.pause()
        assert palette.display is False


@pytest.mark.asyncio
async def test_prompt_composer_localizes_slash_command_palette_in_korean(tmp_path) -> None:
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    )

    async with app.run_test(size=(100, 30)) as pilot:
        composer = app.screen.query_one(PromptComposer)

        composer.set_text("/")
        await pilot.pause()
        options = [str(option.content) for option in composer.query(".command-option")]
        more = str(composer.query_one("#command-option-more").content)

        assert any("/status" in option for option in options)
        assert any("제공자와 워크플로우 상태 보기" in option for option in options)
        assert not any(
            "show provider and workflow status" in option for option in options
        )
        assert "명령 더 있음" in more

        composer.set_text("/missing")
        await pilot.pause()

        empty = str(composer.query_one("#command-option-0").content)
        assert empty == "일치하는 명령이 없습니다"


@pytest.mark.asyncio
async def test_nexus_composer_uses_configured_slash_command_language(tmp_path) -> None:
    app = TrinityTextualApp(
        TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    )

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
        assert _binding_description(
            textarea._bindings, "shift+enter", "insert_newline"
        ) == "새 줄"

        app.switch_to("nexus")
        await pilot.pause()
        nexus = app.screen
        assert isinstance(nexus, NexusScreen)
        assert _binding_description(
            nexus._bindings, "ctrl+e", "request_execute"
        ) == "실행"


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
        selected = [
            str(option.content)
            for option in composer.query(".command-option-selected")
        ]

        assert any("/context" in option for option in selected)

        await pilot.press("enter")
        await pilot.pause()
        assert app.current_route == "start"
        assert composer.text == "/context "


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

        selected = [
            str(option.content)
            for option in composer.query(".command-option-selected")
        ]
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
        assert screen.snapshot is not None
        assert "follow-up: 이어서 검토해줘" in screen.snapshot.work_packages


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
        assert "Questions for you (2)" in str(
            central.query_one("#central-question-title").content
        )
        assert central.query_one("#answer-q-1-1")
        assert central.query_one("#answer-q-1-2")
        assert central.query_one("#answer-q-2-1")
        assert central.query_one("#answer-q-2-2")
        rendered_questions = [
            str(item.content) for item in central.query(".question-text")
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
        assert "Local Command Results" in central._markdown()


@pytest.mark.asyncio
async def test_textual_status_refresh_replaces_existing_local_command_table(
    tmp_path,
) -> None:
    controller = FakeWorkflowController()
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
        assert [
            command.command for command in app.active_snapshot.local_commands
        ].count("/status") == 1

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
        assert "Answer: Godot" in [
            str(item.content) for item in central.query(".question-answer")
        ]
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
            '{\n'
            '  "name": "Trinity",\n'
            '  "items": [\n'
            '    {\n'
            '      "id": 1,\n'
            '      "label": "alpha"\n'
            '    }\n'
            '  ]\n'
            '}'
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
        assert screen.query_one("#execution-table").row_count == 1


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
