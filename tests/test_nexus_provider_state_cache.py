from __future__ import annotations

import pytest
from textual.app import App

from trinity.config import TrinityConfig
from trinity.textual_app.screens.nexus import NexusScreen
from trinity.textual_app.snapshot import ProviderSnapshot, WorkflowNexusSnapshot
from trinity.textual_app.widgets.provider_panel import ProviderPanel


class NexusHarness(App[None]):
    def __init__(self, screen: NexusScreen) -> None:
        super().__init__()
        self.nexus = screen

    def on_mount(self) -> None:
        self.push_screen(self.nexus)


def _snapshot(*, status: str) -> WorkflowNexusSnapshot:
    return WorkflowNexusSnapshot(
        providers=[
            ProviderSnapshot(
                name="claude",
                provider="claude-code",
                enabled=True,
                status=status,
                summary="Provider ready.",
            )
        ]
    )


@pytest.mark.asyncio
async def test_nexus_skips_unchanged_provider_panel_update(tmp_path) -> None:
    screen = NexusScreen(TrinityConfig.default_config(project_dir=tmp_path))
    app = NexusHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        screen.apply_snapshot(_snapshot(status="Ready"))
        await pilot.pause()

        panel = screen.query_one("#provider-claude", ProviderPanel)
        calls: list[str] = []
        original_update = panel.update_state

        def counted_update(state) -> None:
            calls.append(state.status)
            original_update(state)

        panel.update_state = counted_update

        screen.apply_snapshot(_snapshot(status="Ready"))
        await pilot.pause()
        assert calls == []

        screen.apply_snapshot(_snapshot(status="Running"))
        await pilot.pause()
        assert calls == ["Running"]
