from __future__ import annotations

from pathlib import Path

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
async def test_nexus_skips_unchanged_workspace_candidate_refresh(tmp_path) -> None:
    screen = NexusScreen(TrinityConfig.default_config(project_dir=tmp_path))
    app = NexusHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        first = tmp_path / "project-a"
        screen.set_workspace_candidate(first)
        await pilot.pause()

        calls: list[str] = []

        def counted_refresh() -> None:
            calls.append("refresh")

        screen._refresh_workspace_label = counted_refresh

        screen.set_workspace_candidate(Path(str(first)))
        await pilot.pause()
        assert calls == []

        screen.set_workspace_candidate(tmp_path / "project-b")
        await pilot.pause()
        assert calls == ["refresh"]
