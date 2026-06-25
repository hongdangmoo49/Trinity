from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.screen import Screen

from trinity.config import TrinityConfig
from trinity.providers.model_discovery import ProviderModelChoice
from trinity.textual_app.screens.nexus import NexusScreen
from trinity.textual_app.screens.start import StartScreen
from trinity.textual_app.widgets.agent_recipient_model_selector import (
    AgentRecipientModelSelector,
    AgentToggle,
)


class ScreenHarness(App[None]):
    def __init__(self, screen: Screen[None]) -> None:
        super().__init__()
        self.target_screen = screen

    def on_mount(self) -> None:
        self.push_screen(self.target_screen)


class SelectorHarness(App[None]):
    def __init__(self, selector: AgentRecipientModelSelector) -> None:
        super().__init__()
        self.selector = selector

    def compose(self) -> ComposeResult:
        yield self.selector


def _choices(
    config: TrinityConfig,
    *models: str,
    agent: str = "claude",
) -> tuple[ProviderModelChoice, ...]:
    spec = config.agents[agent]
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


@pytest.mark.asyncio
async def test_agent_recipient_selector_uses_cached_toggles(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    selector = AgentRecipientModelSelector(config.agents)
    app = SelectorHarness(selector)
    enabled_agents = tuple(
        name for name, spec in config.agents.items() if spec.enabled
    )
    assert enabled_agents

    async with app.run_test(size=(120, 20)) as pilot:
        await pilot.pause()
        recipient_queries: list[str] = []
        original_query_one = selector.query_one

        def counted_query_one(selector_text, *args, **kwargs):
            if str(selector_text).startswith("#recipient-"):
                recipient_queries.append(str(selector_text))
            return original_query_one(selector_text, *args, **kwargs)

        selector.query_one = counted_query_one

        assert selector.selected_agents() == enabled_agents
        selector.set_selected_agents(enabled_agents[:1])
        await pilot.pause()

        assert selector.selected_agents() == enabled_agents[:1]
        assert recipient_queries == []
        assert selector._toggle_cache[enabled_agents[0]].value is True
        assert isinstance(selector._toggle_cache[enabled_agents[0]], AgentToggle)


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


def test_agent_recipient_selector_skips_unchanged_model_selections(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    selector = AgentRecipientModelSelector(config.agents)

    selector.set_model_selections({"claude": "opus"})
    ensure_calls: list[tuple[str, str]] = []
    set_calls: list[tuple[str, str]] = []
    original_ensure_model_choice = selector._ensure_model_choice
    original_set_selected_model = selector._set_selected_model

    def counted_ensure_model_choice(name: str, model: str) -> None:
        ensure_calls.append((name, model))
        original_ensure_model_choice(name, model)

    def counted_set_selected_model(name: str, model: str) -> None:
        set_calls.append((name, model))
        original_set_selected_model(name, model)

    selector._ensure_model_choice = counted_ensure_model_choice
    selector._set_selected_model = counted_set_selected_model

    selector.set_model_selections({"claude": "opus"})
    assert ensure_calls == []
    assert set_calls == []

    selector.set_model_selections({"claude": "sonnet"})
    assert ensure_calls == [("claude", "sonnet")]
    assert set_calls == [("claude", "sonnet")]
    assert selector.selected_model("claude") == "sonnet"


def test_agent_recipient_selector_skips_unchanged_model_overrides(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    selector = AgentRecipientModelSelector(config.agents)

    selector.set_model_overrides({"claude": "opus"})
    ensure_calls: list[tuple[str, str]] = []
    set_calls: list[tuple[str, str]] = []
    original_ensure_model_choice = selector._ensure_model_choice
    original_set_selected_model = selector._set_selected_model

    def counted_ensure_model_choice(name: str, model: str) -> None:
        ensure_calls.append((name, model))
        original_ensure_model_choice(name, model)

    def counted_set_selected_model(name: str, model: str) -> None:
        set_calls.append((name, model))
        original_set_selected_model(name, model)

    selector._ensure_model_choice = counted_ensure_model_choice
    selector._set_selected_model = counted_set_selected_model

    selector.set_model_overrides({"claude": "opus"})
    assert ensure_calls == []
    assert set_calls == []

    selector.set_model_overrides({"claude": "sonnet"})
    assert ensure_calls == [("claude", "sonnet")]
    assert set_calls == [("claude", "sonnet")]
    assert selector.selected_model("claude") == "sonnet"


@pytest.mark.asyncio
async def test_start_screen_skips_unchanged_model_choices(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    screen = StartScreen(config)
    app = ScreenHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        initial = _choices(config, "default")
        codex_initial = _choices(config, "default", agent="codex")
        screen.set_agent_model_choices(
            {"claude": initial, "codex": codex_initial}
        )
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
        codex_initial = _choices(config, "default", agent="codex")
        screen.set_agent_model_choices(
            {"claude": initial, "codex": codex_initial}
        )
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
