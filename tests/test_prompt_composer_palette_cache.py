from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from trinity.textual_app.widgets.composer import PromptComposer


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
