from __future__ import annotations

import pytest
from textual.app import App
from textual.screen import Screen

from trinity.config import TrinityConfig
from trinity.providers.model_discovery import ProviderModelChoice
from trinity.textual_app.screens.nexus import NexusScreen
from trinity.textual_app.screens.start import StartScreen
from trinity.textual_app.widgets.agent_recipient_model_selector import (
    AgentRecipientModelSelector,
)


class ScreenHarness(App[None]):
    def __init__(self, screen: Screen[None]) -> None:
        super().__init__()
        self.target_screen = screen

    def on_mount(self) -> None:
        self.push_screen(self.target_screen)


def _choices(config: TrinityConfig, *models: str) -> tuple[ProviderModelChoice, ...]:
    spec = config.agents["claude"]
    return tuple(
        ProviderModelChoice(
            provider=spec.provider,
            model=model,
            label=model,
            source="cli-live",
            context_budget=None,
        )
        for model in models
    )


def test_agent_recipient_selector_skips_unchanged_model_choices(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    selector = AgentRecipientModelSelector(config.agents)
    initial = _choices(config, "default")

    selector.set_model_choices("claude", initial)
    calls: list[tuple[str, str]] = []
    original_set_selected_model = selector._set_selected_model

    def counted_set_selected_model(name: str, model: str) -> None:
        calls.append((name, model))
        original_set_selected_model(name, model)

    selector._set_selected_model = counted_set_selected_model

    selector.set_model_choices("claude", tuple(initial))
    assert calls == []

    updated = _choices(config, "default", "opus")
    selector.set_model_choices("claude", updated)

    assert calls == [("claude", "default")]
    assert selector.model_option_labels("claude") == ("default", "opus")


@pytest.mark.asyncio
async def test_start_screen_skips_unchanged_model_choices(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    screen = StartScreen(config)
    app = ScreenHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        initial = _choices(config, "default")
        screen.set_agent_model_choices({"claude": initial})
        await pilot.pause()

        selector = screen.query_one(AgentRecipientModelSelector)
        calls: list[tuple[str, tuple[ProviderModelChoice, ...]]] = []
        original_set_choices = selector.set_model_choices

        def counted_set_model_choices(name, choices) -> None:
            calls.append((name, tuple(choices)))
            original_set_choices(name, choices)

        selector.set_model_choices = counted_set_model_choices

        screen.set_agent_model_choices({"claude": initial})
        await pilot.pause()
        assert calls == []

        updated = _choices(config, "default", "opus")
        screen.set_agent_model_choices({"claude": updated})
        await pilot.pause()
        assert calls == [("claude", updated)]


@pytest.mark.asyncio
async def test_nexus_screen_skips_unchanged_model_choices(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    screen = NexusScreen(config)
    app = ScreenHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        initial = _choices(config, "default")
        screen.set_agent_model_choices({"claude": initial})
        await pilot.pause()

        selector = screen.query_one(AgentRecipientModelSelector)
        calls: list[tuple[str, tuple[ProviderModelChoice, ...]]] = []
        original_set_choices = selector.set_model_choices

        def counted_set_model_choices(name, choices) -> None:
            calls.append((name, tuple(choices)))
            original_set_choices(name, choices)

        selector.set_model_choices = counted_set_model_choices

        screen.set_agent_model_choices({"claude": initial})
        await pilot.pause()
        assert calls == []

        updated = _choices(config, "default", "opus")
        screen.set_agent_model_choices({"claude": updated})
        await pilot.pause()
        assert calls == [("claude", updated)]
