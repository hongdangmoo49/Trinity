from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import Static

from trinity.config import TrinityConfig
from trinity.textual_app.screens.start import StartScreen


class StartScreenHarness(App[None]):
    def __init__(self, screen: StartScreen) -> None:
        super().__init__()
        self.target_screen = screen

    def on_mount(self) -> None:
        self.push_screen(self.target_screen)


@pytest.mark.asyncio
async def test_start_workspace_label_skips_unchanged_update(tmp_path: Path) -> None:
    control_repo = tmp_path / "control"
    target = tmp_path / "target"
    next_target = tmp_path / "next"
    control_repo.mkdir()
    target.mkdir()
    next_target.mkdir()
    screen = StartScreen(
        TrinityConfig.default_config(project_dir=control_repo),
        workspace_candidate=target,
    )
    app = StartScreenHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        label = screen.query_one("#workspace-candidate", Static)
        updates: list[str] = []
        original_update = label.update

        def counted_update(content) -> None:
            updates.append(str(content))
            original_update(content)

        label.update = counted_update

        screen.set_workspace_candidate(target)
        await pilot.pause()
        assert updates == []

        screen.set_workspace_candidate(next_target)
        await pilot.pause()
        assert updates == [f"Target workspace: {next_target}"]
