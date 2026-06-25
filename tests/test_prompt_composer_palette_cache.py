from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from trinity.textual_app.widgets.composer import (
    COMMAND_LIMIT,
    ComposerTextArea,
    PromptComposer,
)


class ComposerHarness(App[None]):
    def __init__(self, composer: PromptComposer) -> None:
        super().__init__()
        self.composer = composer

    def compose(self) -> ComposeResult:
        yield self.composer


@pytest.mark.asyncio
async def test_prompt_composer_skips_unchanged_palette_render() -> None:
    composer = PromptComposer()
    app = ComposerHarness(composer)

    async with app.run_test(size=(100, 24)) as pilot:
        composer.set_text("/sta")
        await pilot.pause()

        updates: list[str] = []
        for option in composer.query(".command-option"):
            static = option
            assert isinstance(static, Static)
            original_update = static.update

            def counted_update(content, original_update=original_update) -> None:
                updates.append(str(content))
                original_update(content)

            static.update = counted_update

        composer._refresh_command_palette()
        await pilot.pause()

        assert updates == []

        composer.set_text("/rep")
        await pilot.pause()

        assert updates


@pytest.mark.asyncio
async def test_prompt_composer_skips_inactive_palette_refresh() -> None:
    composer = PromptComposer()
    app = ComposerHarness(composer)

    async with app.run_test(size=(100, 24)) as pilot:
        composer.set_text("plain text")
        await pilot.pause()

        calls: list[str] = []

        def counted_render_options() -> None:
            calls.append("render")

        def counted_set_visible(visible: bool) -> None:
            calls.append(f"visible:{visible}")

        composer._render_command_options = counted_render_options
        composer._set_command_palette_visible = counted_set_visible

        composer.set_text("plain text updated")
        await pilot.pause()

        assert calls == []


@pytest.mark.asyncio
async def test_prompt_composer_selection_move_updates_only_changed_option_rows() -> None:
    composer = PromptComposer()
    app = ComposerHarness(composer)

    async with app.run_test(size=(100, 24)) as pilot:
        composer.set_text("/")
        await pilot.pause()
        assert len(composer._command_matches) > 1

        updates: list[str] = []
        for option in composer.query(".command-option"):
            static = option
            assert isinstance(static, Static)
            original_update = static.update

            def counted_update(content, original_update=original_update) -> None:
                updates.append(str(content))
                original_update(content)

            static.update = counted_update

        option_queries: list[str] = []
        original_query_one = composer.query_one

        def counted_query_one(selector, *args, **kwargs):
            if str(selector).startswith("#command-option-"):
                option_queries.append(str(selector))
            return original_query_one(selector, *args, **kwargs)

        composer.query_one = counted_query_one

        composer.move_command_selection(1)
        await pilot.pause()

        assert updates == []
        assert option_queries == []


@pytest.mark.asyncio
async def test_prompt_composer_reuses_composed_fixed_widgets() -> None:
    composer = PromptComposer()
    app = ComposerHarness(composer)

    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        query_calls: list[object] = []
        original_query_one = composer.query_one
        fixed_selectors = {
            ComposerTextArea,
            "#prompt-command-palette",
            "#command-option-more",
            *{f"#command-option-{index}" for index in range(COMMAND_LIMIT)},
        }

        def counted_query_one(selector, *args, **kwargs):
            if selector in fixed_selectors:
                query_calls.append(selector)
            return original_query_one(selector, *args, **kwargs)

        composer.query_one = counted_query_one

        composer.set_text("/sta")
        composer.move_command_selection(1)
        composer.focus_text_area()
        composer.action_insert_newline()
        _ = composer.submission_text
        _ = composer.command_palette_open
        await pilot.pause()

        assert query_calls == []


@pytest.mark.asyncio
async def test_prompt_composer_rebinds_palette_render_keys_after_recompose() -> None:
    composer = PromptComposer()
    app = ComposerHarness(composer)

    async with app.run_test(size=(100, 24)) as pilot:
        composer.set_text("/sta")
        await pilot.pause()

        assert any(
            "/status" in str(option.content)
            for option in composer.query(".command-option")
        )

        composer.refresh(recompose=True)
        await pilot.pause()

        composer.set_text("/sta")
        await pilot.pause()

        assert composer.query_one("#prompt-command-palette").display is True
        assert any(
            "/status" in str(option.content)
            for option in composer.query(".command-option")
        )


@pytest.mark.asyncio
async def test_prompt_composer_set_text_skips_same_text_without_pastes() -> None:
    composer = PromptComposer()
    app = ComposerHarness(composer)

    async with app.run_test(size=(100, 24)) as pilot:
        composer.set_text("plain text")
        await pilot.pause()

        text_area = composer.query_one(ComposerTextArea)
        load_calls: list[str] = []
        refresh_calls: list[str] = []
        original_load_text = text_area.load_text
        original_refresh = composer._refresh_command_palette

        def counted_load_text(text: str) -> None:
            load_calls.append(text)
            original_load_text(text)

        def counted_refresh() -> None:
            refresh_calls.append("refresh")
            original_refresh()

        text_area.load_text = counted_load_text
        composer._refresh_command_palette = counted_refresh

        composer.set_text("plain text")
        await pilot.pause()
        assert load_calls == []
        assert refresh_calls == []

        composer.set_text("changed text")
        await pilot.pause()
        assert load_calls == ["changed text"]
        assert refresh_calls


@pytest.mark.asyncio
async def test_prompt_composer_set_text_preserves_paste_clear_refresh() -> None:
    composer = PromptComposer()
    app = ComposerHarness(composer)

    async with app.run_test(size=(100, 24)) as pilot:
        placeholder = composer.register_pasted_content("long\npaste")
        composer.set_text(placeholder, clear_pastes=False)
        await pilot.pause()
        assert composer._pasted_content

        text_area = composer.query_one(ComposerTextArea)
        load_calls: list[str] = []
        refresh_calls: list[str] = []
        original_load_text = text_area.load_text
        original_refresh = composer._refresh_command_palette

        def counted_load_text(text: str) -> None:
            load_calls.append(text)
            original_load_text(text)

        def counted_refresh() -> None:
            refresh_calls.append("refresh")
            original_refresh()

        text_area.load_text = counted_load_text
        composer._refresh_command_palette = counted_refresh

        composer.set_text(placeholder)
        await pilot.pause()

        assert composer._pasted_content == []
        assert load_calls == [placeholder]
        assert refresh_calls
