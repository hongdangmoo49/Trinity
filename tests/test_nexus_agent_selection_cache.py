from __future__ import annotations

import pytest
from textual.app import App

from trinity.config import TrinityConfig
from trinity.textual_app.screens.nexus import NexusScreen


class NexusHarness(App[None]):
    def __init__(self, screen: NexusScreen) -> None:
        super().__init__()
        self.nexus = screen

    def on_mount(self) -> None:
        self.push_screen(self.nexus)


@pytest.mark.asyncio
async def test_nexus_skips_unchanged_agent_selection_apply(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents["codex"].enabled = True
    screen = NexusScreen(config)
    app = NexusHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        screen.set_agent_selection(("claude",), {"claude": "default"})
        await pilot.pause()

        calls: list[str] = []

        def counted_apply() -> None:
            calls.append("apply")

        screen._apply_agent_selection = counted_apply

        screen.set_agent_selection(["claude"], {"claude": "default"})
        await pilot.pause()
        assert calls == []

        screen.set_agent_selection(("codex",), {"codex": "gpt-5"})
        await pilot.pause()
        assert calls == ["apply"]
