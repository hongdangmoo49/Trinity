from __future__ import annotations

import pytest
from textual import events
from textual.widgets import Button, RichLog, TabbedContent, TextArea

from trinity.config import TrinityConfig
from trinity.textual_app.app import TrinityTextualApp
from trinity.textual_app.screens.execution_matrix import ExecutionMatrixScreen
from trinity.textual_app.screens.nexus import NexusScreen
from trinity.textual_app.screens.settings import SettingsScreen
from trinity.textual_app.screens.start import StartScreen
from trinity.textual_app.settings import UISettingsStore
from trinity.textual_app.snapshot import (
    ProviderSnapshot,
    QuestionSnapshot,
    SynthesisSnapshot,
    WorkflowNexusSnapshot,
)
from trinity.textual_app.workflow_controller import TextualWorkflowOutcome
from trinity.textual_app.widgets.central_agent import CentralAgentView
from trinity.textual_app.widgets.composer import COMMAND_LIMIT, PromptComposer
from trinity.textual_app.widgets.inspector import WorkflowInspector
from trinity.textual_app.widgets.provider_inspector import ProviderInspector
from trinity.textual_app.widgets.provider_panel import ProviderPanel
from trinity.textual_app.widgets.workspace_picker import WorkspacePicker, build_preflight
from trinity.workflow import WorkflowPersistence, WorkflowSession, WorkflowState


class FakeWorkflowController:
    def __init__(self, snapshot: WorkflowNexusSnapshot | None = None) -> None:
        self.current_snapshot = snapshot or WorkflowNexusSnapshot()
        self.started_prompts: list[str] = []
        self.follow_ups: list[str] = []
        self.answers: list[tuple[str, str]] = []
        self.execution_requests = 0
        self.target_workspace = None

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

    def answer_question(self, question_id: str, answer: str) -> TextualWorkflowOutcome:
        self.answers.append((question_id, answer))
        self.current_snapshot = WorkflowNexusSnapshot(
            session_id="wf-fake",
            goal=self.current_snapshot.goal,
            state="deliberating",
            decisions=[answer],
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

    def new_session(self) -> TextualWorkflowOutcome:
        self.current_snapshot = WorkflowNexusSnapshot()
        return TextualWorkflowOutcome(self.current_snapshot)

    def drain_updates(self):
        return None


@pytest.mark.asyncio
async def test_textual_app_boots_to_start_screen(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(100, 30)):
        assert app.current_route == "start"
        assert app.screen.name == "start"
        assert app.screen.query_one(PromptComposer)


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
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path), FakeWorkflowController())

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

        composer.set_text("hello /status")
        await pilot.pause()
        assert palette.display is False


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
async def test_central_agent_view_renders_only_next_question(tmp_path) -> None:
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
        assert "Question for you (1 of 2)" in str(
            central.query_one("#central-question-title").content
        )
        assert central.query_one("#answer-q-1-1")
        assert central.query_one("#answer-q-1-2")
        assert not central.query("#answer-q-2-1")
        rendered_questions = [
            str(item.content) for item in central.query(".question-text")
        ]
        assert rendered_questions == ["1. Engine?"]


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
        assert panel.has_class("provider-running")
        assert "Running" in str(panel.query_one(".provider-status").content)
        assert central.has_class("central-running")
        assert "Central Agent" in str(central.query_one("#central-title").content)
        assert "round 1 synthesizing" in central._markdown()

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

        assert controller.answers == [("q-1", "dark")]


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
