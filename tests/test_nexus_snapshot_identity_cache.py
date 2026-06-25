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


def _snapshot(*, status: str = "Ready", summary: str = "Ready.") -> WorkflowNexusSnapshot:
    return WorkflowNexusSnapshot(
        session_id="wf-nexus-cache",
        state="reviewing",
        providers=[
            ProviderSnapshot(
                name="claude",
                provider="claude-code",
                enabled=True,
                status=status,
                summary=summary,
            )
        ],
    )


@pytest.mark.asyncio
async def test_nexus_skips_reapplying_same_snapshot_object(tmp_path) -> None:
    screen = NexusScreen(TrinityConfig.default_config(project_dir=tmp_path))
    snapshot = _snapshot()
    app = NexusHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        screen.apply_snapshot(snapshot)
        await pilot.pause()

        calls: list[str] = []

        def counted_central() -> None:
            calls.append("central")

        def counted_questions() -> None:
            calls.append("questions")

        def counted_inspector() -> None:
            calls.append("inspector")

        screen._refresh_central = counted_central
        screen._refresh_questions = counted_questions
        screen._refresh_inspector = counted_inspector

        screen.apply_snapshot(snapshot)
        await pilot.pause()
        assert calls == []

        screen.apply_snapshot(_snapshot())
        await pilot.pause()
        assert calls == ["central", "questions", "inspector"]


@pytest.mark.asyncio
async def test_nexus_provider_update_invalidates_snapshot_identity_cache(tmp_path) -> None:
    screen = NexusScreen(TrinityConfig.default_config(project_dir=tmp_path))
    snapshot = _snapshot(status="Ready", summary="Ready.")
    app = NexusHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        screen.apply_snapshot(snapshot)
        await pilot.pause()

        screen.update_provider("claude", status="Running", summary="Runtime progress.")
        await pilot.pause()
        panel = screen.query_one("#provider-claude", ProviderPanel)
        assert "Runtime progress." in str(panel.query_one(".provider-summary").content)

        screen.apply_snapshot(snapshot)
        await pilot.pause()

        assert "Ready." in str(panel.query_one(".provider-summary").content)
