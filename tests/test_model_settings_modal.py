from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import Button, OptionList

from trinity.config import TrinityConfig
from trinity.providers.model_discovery import ProviderModelChoice
from trinity.textual_app.widgets.model_settings_modal import ModelSettingsModal


class ModelSettingsModalHarness(App[None]):
    def __init__(self, modal: ModelSettingsModal) -> None:
        super().__init__()
        self.modal = modal

    def on_mount(self) -> None:
        self.push_screen(self.modal)


@pytest.mark.asyncio
async def test_model_settings_modal_skips_unchanged_choice_refresh(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    spec = config.agents["codex"]
    initial_choices = (
        ProviderModelChoice(
            provider=spec.provider,
            model="default",
            label="default",
            source="static-fallback",
            context_budget=None,
        ),
    )
    modal = ModelSettingsModal(
        config.agents,
        {"codex": initial_choices},
        {"codex": "default"},
    )
    app = ModelSettingsModalHarness(modal)

    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        refresh_calls: list[bool] = []

        def counted_refresh() -> None:
            refresh_calls.append(True)

        modal._refresh_choices = counted_refresh

        modal.set_model_choices({"codex": initial_choices})
        await pilot.pause()
        assert refresh_calls == []

        updated_choices = (
            *initial_choices,
            ProviderModelChoice(
                provider=spec.provider,
                model="gpt-5.5",
                label="gpt-5.5",
                source="cli-live",
                context_budget=None,
            ),
        )
        modal.set_model_choices({"codex": updated_choices})
        await pilot.pause()

        assert refresh_calls == [True]
        assert modal.choices_by_agent["codex"] == updated_choices


@pytest.mark.asyncio
async def test_model_settings_modal_skips_active_agent_reselect_refresh(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    choices = {
        name: (
            ProviderModelChoice(
                provider=spec.provider,
                model="default",
                label="default",
                source="static-fallback",
                context_budget=None,
            ),
        )
        for name, spec in config.agents.items()
    }
    modal = ModelSettingsModal(config.agents, choices, {})
    app = ModelSettingsModalHarness(modal)

    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        assert modal.active_agent == "claude"
        refresh_calls: list[bool] = []

        def counted_refresh() -> None:
            refresh_calls.append(True)

        modal._refresh_choices = counted_refresh

        modal.query_one("#model-agent-claude", Button).press()
        await pilot.pause()

        assert refresh_calls == []
        assert modal.active_agent == "claude"

        modal.query_one("#model-agent-codex", Button).press()
        await pilot.pause()

        assert refresh_calls == [True]
        assert modal.active_agent == "codex"


@pytest.mark.asyncio
async def test_model_settings_modal_skips_selected_option_refresh(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    spec = config.agents["claude"]
    choices = (
        ProviderModelChoice(
            provider=spec.provider,
            model="default",
            label="default",
            source="static-fallback",
            context_budget=None,
        ),
        ProviderModelChoice(
            provider=spec.provider,
            model="opus",
            label="opus",
            source="cli-live",
            context_budget=None,
        ),
    )
    modal = ModelSettingsModal(
        config.agents,
        {"claude": choices},
        {"claude": "default"},
    )
    app = ModelSettingsModalHarness(modal)

    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        refresh_calls: list[bool] = []

        def counted_refresh() -> None:
            refresh_calls.append(True)

        modal._refresh_choices = counted_refresh
        option_list = modal.query_one("#model-choice-list", OptionList)

        option_list.highlighted = 0
        option_list.action_select()
        await pilot.pause()

        assert refresh_calls == []
        assert modal.selected_models["claude"] == "default"

        option_list.highlighted = 1
        option_list.action_select()
        await pilot.pause()

        assert refresh_calls == [True]
        assert modal.selected_models["claude"] == "opus"


@pytest.mark.asyncio
async def test_model_settings_modal_skips_unchanged_highlight_sync(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    spec = config.agents["claude"]
    choices = (
        ProviderModelChoice(
            provider=spec.provider,
            model="default",
            label="default",
            source="static-fallback",
            context_budget=None,
        ),
        ProviderModelChoice(
            provider=spec.provider,
            model="opus",
            label="opus",
            source="cli-live",
            context_budget=None,
        ),
    )
    modal = ModelSettingsModal(
        config.agents,
        {"claude": choices},
        {"claude": "default"},
    )
    app = ModelSettingsModalHarness(modal)

    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        option_list = modal.query_one("#model-choice-list", OptionList)
        query_calls: list[str] = []
        original_query_one = modal.query_one

        def counted_query_one(selector, *args, **kwargs):
            if selector == "#model-choice-list":
                query_calls.append(str(selector))
            return original_query_one(selector, *args, **kwargs)

        modal.query_one = counted_query_one

        modal._sync_choice_highlight()
        await pilot.pause()
        assert query_calls == []

        modal.selected_models["claude"] = "opus"
        modal._sync_choice_highlight()
        await pilot.pause()

        assert query_calls == []
        assert option_list.highlighted == 1


@pytest.mark.asyncio
async def test_model_settings_modal_rebinds_choice_list_cache_after_refresh(
    tmp_path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    choices = {
        name: (
            ProviderModelChoice(
                provider=spec.provider,
                model="default",
                label="default",
                source="static-fallback",
                context_budget=None,
            ),
            ProviderModelChoice(
                provider=spec.provider,
                model=f"{name}-next",
                label=f"{name}-next",
                source="cli-live",
                context_budget=None,
            ),
        )
        for name, spec in config.agents.items()
    }
    modal = ModelSettingsModal(
        config.agents,
        choices,
        {"claude": "default", "codex": "codex-next"},
    )
    app = ModelSettingsModalHarness(modal)

    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        first_choice_list = modal._choice_list_widget
        codex_button = modal.query_one("#model-agent-codex", Button)
        query_calls: list[str] = []
        original_query_one = modal.query_one

        def counted_query_one(selector, *args, **kwargs):
            if selector == "#model-choice-list":
                query_calls.append(str(selector))
            return original_query_one(selector, *args, **kwargs)

        modal.query_one = counted_query_one

        codex_button.press()
        await pilot.pause()

        assert query_calls == []
        assert modal._choice_list_widget is not None
        assert modal._choice_list_widget is not first_choice_list
        assert modal._choice_list_widget.highlighted == 1
