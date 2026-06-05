from __future__ import annotations

import pytest

from trinity.config import TrinityConfig
from trinity.textual_app.app import TrinityTextualApp
from trinity.textual_app.screens.nexus import NexusScreen
from trinity.textual_app.screens.start import StartScreen
from trinity.textual_app.widgets.composer import PromptComposer
from trinity.textual_app.widgets.provider_panel import ProviderPanel


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
