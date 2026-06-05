from __future__ import annotations

import pytest

from trinity.config import TrinityConfig
from trinity.textual_app.app import TrinityTextualApp
from trinity.textual_app.screens.execution_matrix import ExecutionMatrixScreen
from trinity.textual_app.screens.nexus import NexusScreen
from trinity.textual_app.screens.settings import SettingsScreen
from trinity.textual_app.screens.start import StartScreen
from trinity.textual_app.settings import UISettingsStore
from trinity.textual_app.snapshot import ProviderSnapshot, QuestionSnapshot, WorkflowNexusSnapshot
from trinity.textual_app.widgets.central_agent import CentralAgentView
from trinity.textual_app.widgets.composer import PromptComposer
from trinity.textual_app.widgets.inspector import WorkflowInspector
from trinity.textual_app.widgets.provider_inspector import ProviderInspector
from trinity.textual_app.widgets.provider_panel import ProviderPanel
from trinity.textual_app.widgets.workspace_picker import WorkspacePicker, build_preflight


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
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

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


@pytest.mark.asyncio
async def test_start_composer_enter_key_submits_prompt(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

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
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

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
async def test_provider_inspector_all_tab_uses_scrollable_markdown(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(
            ProviderInspector(
                [
                    ProviderSnapshot(
                        name="claude",
                        provider="claude-code",
                        enabled=True,
                        status="Ready",
                        raw_output="\\n".join(f"line {index}" for index in range(200)),
                    )
                ]
            )
        )
        await pilot.pause()

        markdown = app.screen.query_one("#inspect-all .provider-inspector-markdown")
        assert markdown.styles.height.value == 1
        assert markdown.styles.overflow_y == "auto"


@pytest.mark.asyncio
async def test_workspace_picker_opens_from_nexus_execute(tmp_path) -> None:
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(140, 44)) as pilot:
        app.switch_to("nexus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NexusScreen)
        screen.action_request_execute()
        await pilot.pause()

        assert isinstance(app.screen, WorkspacePicker)
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
