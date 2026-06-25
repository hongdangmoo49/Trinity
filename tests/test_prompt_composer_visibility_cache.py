from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from trinity.textual_app.widgets.composer import PromptComposer


class ComposerHarness(App[None]):
    def __init__(self, composer: PromptComposer) -> None:
        super().__init__()
        self.composer = composer

    def compose(self) -> ComposeResult:
        yield self.composer


@pytest.mark.asyncio
async def test_prompt_composer_skips_unchanged_palette_visibility() -> None:
    composer = PromptComposer()
    app = ComposerHarness(composer)

    async with app.run_test(size=(100, 24)) as pilot:
        composer._set_command_palette_visible(True)
        await pilot.pause()

        class_calls: list[bool] = []
        original_set_class = composer.set_class

        def counted_set_class(add: bool, class_name: str) -> None:
            if class_name == "-commands-open":
                class_calls.append(add)
            original_set_class(add, class_name)

        composer.set_class = counted_set_class

        composer._set_command_palette_visible(True)
        await pilot.pause()
        assert class_calls == []

        composer._set_command_palette_visible(False)
        await pilot.pause()
        assert class_calls == [False]
