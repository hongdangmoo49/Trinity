from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import Static

from trinity.config import TrinityConfig
from trinity.textual_app.presenters import nexus_current_workspace_text
from trinity.textual_app.screens.nexus import NexusScreen
from trinity.textual_app.snapshot import WorkflowNexusSnapshot


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


@pytest.mark.asyncio
async def test_nexus_keeps_snapshot_target_when_fallback_candidate_changes(
    tmp_path,
) -> None:
    active = tmp_path / "active-project"
    fallback = tmp_path / "fallback-project"
    active.mkdir()
    fallback.mkdir()
    assert nexus_current_workspace_text(None, fallback) == str(fallback)
    screen = NexusScreen(TrinityConfig.default_config(project_dir=tmp_path))
    screen.snapshot = WorkflowNexusSnapshot(target_workspace=str(active))
    app = NexusHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()

        screen.set_workspace_candidate(fallback)
        await pilot.pause()

        assert nexus_current_workspace_text(screen.snapshot, fallback) == str(active)
        assert str(active) in str(
            screen.query_one("#nexus-target-workspace", Static).content
        )
