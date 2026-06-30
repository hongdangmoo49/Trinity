from __future__ import annotations

import pytest
from textual.app import App

from trinity.config import TrinityConfig
from trinity.textual_app.presenters import nexus_central_snapshot_has_activity
from trinity.textual_app.screens.nexus import NexusScreen
from trinity.textual_app.snapshot import (
    ProviderSnapshot,
    SynthesisSnapshot,
    WorkflowNexusSnapshot,
)


class NexusHarness(App[None]):
    def __init__(self, screen: NexusScreen) -> None:
        super().__init__()
        self.nexus = screen

    def on_mount(self) -> None:
        self.push_screen(self.nexus)


def test_nexus_central_snapshot_has_activity() -> None:
    assert nexus_central_snapshot_has_activity(
        WorkflowNexusSnapshot(state="blueprint_ready")
    ) is False
    assert nexus_central_snapshot_has_activity(
        WorkflowNexusSnapshot(state="deliberating")
    ) is True
    assert nexus_central_snapshot_has_activity(
        WorkflowNexusSnapshot(
            state="blueprint_ready",
            synthesis=SynthesisSnapshot(status="waiting"),
        )
    ) is True


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


@pytest.mark.asyncio
async def test_nexus_idle_activity_tick_skips_widget_queries(
    tmp_path,
    monkeypatch,
) -> None:
    screen = NexusScreen(TrinityConfig.default_config(project_dir=tmp_path))
    app = NexusHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
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

        query_calls: list[str] = []
        original_query = screen.query
        original_query_one = screen.query_one

        def counted_query(*args, **kwargs):
            query_calls.append(str(args[0]) if args else "")
            return original_query(*args, **kwargs)

        def counted_query_one(*args, **kwargs):
            query_calls.append(str(args[0]) if args else "")
            return original_query_one(*args, **kwargs)

        monkeypatch.setattr(screen, "query", counted_query)
        monkeypatch.setattr(screen, "query_one", counted_query_one)

        previous_frame = screen._activity_frame
        screen.advance_activity_frame()
        await pilot.pause()

        assert screen._activity_frame == previous_frame
        assert query_calls == []


@pytest.mark.asyncio
async def test_nexus_direct_provider_update_keeps_activity_tick(
    tmp_path,
) -> None:
    screen = NexusScreen(TrinityConfig.default_config(project_dir=tmp_path))
    app = NexusHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
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
        screen.update_provider("claude", status="Running", summary="Runtime progress.")
        await pilot.pause()

        calls: list[int] = []

        def counted_activity_frame() -> None:
            calls.append(screen._activity_frame)

        screen._apply_activity_frame = counted_activity_frame

        screen.advance_activity_frame()
        await pilot.pause()

        assert screen._activity_frame == 1
        assert calls == [1]
