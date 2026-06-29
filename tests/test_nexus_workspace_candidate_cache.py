from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App

from trinity.config import TrinityConfig
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
async def test_nexus_skips_full_project_refresh_when_snapshot_target_owns_context(
    tmp_path,
) -> None:
    active = tmp_path / "active-project"
    fallback = tmp_path / "fallback-project"
    active.mkdir()
    fallback.mkdir()
    screen = NexusScreen(TrinityConfig.default_config(project_dir=tmp_path))
    screen.snapshot = WorkflowNexusSnapshot(target_workspace=str(active))
    app = NexusHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()

        calls: list[str] = []

        def counted_refresh() -> None:
            calls.append("refresh")

        screen.refresh_project_intake_summary = counted_refresh

        screen.set_workspace_candidate(fallback)
        await pilot.pause()

        assert calls == []
