from __future__ import annotations

import pytest
from textual.app import App

from trinity.config import TrinityConfig
from trinity.textual_app.screens.nexus import NexusScreen
from trinity.textual_app.snapshot import ProviderSnapshot, WorkflowNexusSnapshot


class NexusHarness(App[None]):
    def __init__(self, screen: NexusScreen) -> None:
        super().__init__()
        self.nexus = screen

    def on_mount(self) -> None:
        self.push_screen(self.nexus)


@pytest.mark.asyncio
async def test_nexus_skips_activity_frame_for_idle_snapshot(tmp_path) -> None:
    screen = NexusScreen(TrinityConfig.default_config(project_dir=tmp_path))
    app = NexusHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        calls: list[str] = []

        def counted_activity_frame() -> None:
            calls.append("frame")

        screen._apply_activity_frame = counted_activity_frame

        screen.apply_snapshot(
            WorkflowNexusSnapshot(
                state="blueprint_ready",
                providers=[
                    ProviderSnapshot(
                        name="claude",
                        provider="claude-code",
                        enabled=True,
                        status="Ready",
                    )
                ],
            )
        )
        await pilot.pause()
        assert calls == []

        screen.apply_snapshot(
            WorkflowNexusSnapshot(
                state="blueprint_ready",
                providers=[
                    ProviderSnapshot(
                        name="claude",
                        provider="claude-code",
                        enabled=True,
                        status="Running",
                    )
                ],
            )
        )
        await pilot.pause()
        assert calls == ["frame"]
