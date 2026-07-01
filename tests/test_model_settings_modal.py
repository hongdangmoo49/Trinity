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
async def test_model_settings_modal_refresh_preserves_selected_model(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    spec = config.agents["claude"]
    default_choice = ProviderModelChoice(
        provider=spec.provider,
        model="default",
        label="default",
        source="static-fallback",
        context_budget=None,
    )
    custom_choice = ProviderModelChoice(
        provider=spec.provider,
        model="custom-live",
        label="custom-live",
        source="static-fallback",
        context_budget=None,
    )
    modal = ModelSettingsModal(
        config.agents,
        {"claude": (default_choice, custom_choice)},
        {"claude": "custom-live"},
    )
    app = ModelSettingsModalHarness(modal)

    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()

        live_choice = ProviderModelChoice(
            provider=spec.provider,
            model="opus-live",
            label="opus-live",
            source="cli-live",
            context_budget=None,
        )
        modal.set_model_choices({"claude": (default_choice, live_choice)})
        await pilot.pause()

        choices = modal.choices_by_agent["claude"]
        option_list = modal.query_one("#model-choice-list", OptionList)

        assert [choice.model for choice in choices] == [
            "default",
            "opus-live",
            "custom-live",
        ]
        assert modal.selected_models["claude"] == "custom-live"
        assert option_list.highlighted == 2


@pytest.mark.asyncio
async def test_model_settings_modal_keeps_missing_default_first(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents["codex"].enabled = True
    spec = config.agents["codex"]
    live_choice = ProviderModelChoice(
        provider=spec.provider,
        model="gpt-5.5",
        label="gpt-5.5",
        source="cli-live",
        context_budget=None,
    )
    modal = ModelSettingsModal(
        config.agents,
        {"codex": (live_choice,)},
        {"codex": "default"},
    )
    app = ModelSettingsModalHarness(modal)

    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        modal.query_one("#model-agent-codex", Button).press()
        await pilot.pause()

        option_list = modal.query_one("#model-choice-list", OptionList)
        choices = modal.choices_by_agent["codex"]

        assert [choice.model for choice in choices] == ["default", "gpt-5.5"]
        assert option_list.highlighted == 0


@pytest.mark.asyncio
async def test_model_settings_modal_moves_existing_default_first(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents["codex"].enabled = True
    spec = config.agents["codex"]
    default_choice = ProviderModelChoice(
        provider=spec.provider,
        model="default",
        label="codex(default)",
        source="static-fallback",
        context_budget=128_000,
    )
    live_choice = ProviderModelChoice(
        provider=spec.provider,
        model="gpt-5.5",
        label="gpt-5.5",
        source="cli-live",
        context_budget=None,
    )
    modal = ModelSettingsModal(
        config.agents,
        {"codex": (live_choice, default_choice)},
        {"codex": "default"},
    )
    app = ModelSettingsModalHarness(modal)

    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        modal.query_one("#model-agent-codex", Button).press()
        await pilot.pause()

        choices = modal.choices_by_agent["codex"]
        option_list = modal.query_one("#model-choice-list", OptionList)

        assert [choice.model for choice in choices] == ["default", "gpt-5.5"]
        assert choices[0].label == "codex(default)"
        assert option_list.highlighted == 0


@pytest.mark.asyncio
async def test_model_settings_modal_starts_on_first_enabled_agent(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents["claude"].enabled = False
    config.agents["codex"].enabled = True
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
        choice_header = modal.query_one("#model-choice-header")

        assert modal.active_agent == "codex"
        assert "Codex" in str(choice_header.content)
        assert str(modal.query_one("#model-agent-codex", Button).label).startswith("> ")
        claude_button = modal.query_one("#model-agent-claude", Button)
        assert "off" in str(claude_button.label)
        assert claude_button.disabled is True

        claude_button.press()
        await pilot.pause()

        assert modal.active_agent == "codex"


@pytest.mark.asyncio
async def test_model_settings_modal_uses_korean_disabled_agent_label(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    config.agents["claude"].enabled = False
    config.agents["codex"].enabled = True
    modal = ModelSettingsModal(config.agents, {}, {}, lang="ko")
    app = ModelSettingsModalHarness(modal)

    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()

        claude_button = modal.query_one("#model-agent-claude", Button)

    assert "비활성" in str(claude_button.label)
    assert "off" not in str(claude_button.label)


@pytest.mark.asyncio
async def test_model_settings_modal_skips_active_agent_reselect_refresh(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents["codex"].enabled = True
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
    config.agents["codex"].enabled = True
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


@pytest.mark.asyncio
async def test_model_settings_modal_keeps_actions_inside_narrow_viewport(
    tmp_path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    choices = {
        name: tuple(
            ProviderModelChoice(
                provider=spec.provider,
                model=f"{name}-very-long-model-identifier-{index}",
                label=f"{name} very long model label {index} with extra details",
                source="cli-live",
                context_budget=1_000_000 + index,
            )
            for index in range(12)
        )
        for name, spec in config.agents.items()
    }
    modal = ModelSettingsModal(config.agents, choices, {}, lang="en")
    app = ModelSettingsModalHarness(modal)

    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        shell = modal.query_one("#model-settings-modal")

        for widget_id in (
            "#model-settings-title",
            "#model-settings-body",
            "#model-settings-actions",
            "#cancel-model-settings",
            "#apply-model-settings",
        ):
            widget = modal.query_one(widget_id)
            assert widget.region.y >= shell.region.y
            assert widget.region.y + widget.region.height <= (
                shell.region.y + shell.region.height
            )
