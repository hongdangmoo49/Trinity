from __future__ import annotations

import pytest
from textual.app import App

from trinity.config import TrinityConfig
from trinity.textual_app.presenters import (
    nexus_agent_provider_panel_state,
    nexus_central_snapshot_has_activity,
    nexus_fallback_snapshot,
    nexus_provider_panel_state,
)
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


def test_nexus_provider_panel_state_maps_provider_snapshot() -> None:
    state = nexus_provider_panel_state(
        ProviderSnapshot(
            name="codex",
            provider="codex-cli",
            enabled=True,
            status="Running",
            summary="Working",
            response_status="ok",
            configured_model="default",
            actual_model="gpt-test",
            context_window=123,
            output_contract="execute-v1",
            quality_score=0.75,
        )
    )

    assert state.name == "codex"
    assert state.status == "Running"
    assert state.actual_model == "gpt-test"
    assert state.context_window == 123
    assert state.output_contract == "execute-v1"
    assert state.quality_score == 0.75


def test_nexus_agent_provider_panel_state_maps_config_agent(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    spec = config.agents["claude"]

    state = nexus_agent_provider_panel_state(
        "claude",
        spec,
        status="Running",
        summary="Runtime progress.",
    )

    assert state.name == "claude"
    assert state.provider == spec.provider.value
    assert state.status == "Running"
    assert state.summary == "Runtime progress."
    assert state.configured_model == spec.model
    assert state.context_window == spec.effective_context_budget
    assert state.budget_source == "trinity_config"


def test_nexus_fallback_snapshot_keeps_recent_followups() -> None:
    snapshot = nexus_fallback_snapshot(
        "Initial goal",
        ["first", "second", "third", "fourth"],
    )

    assert snapshot.goal == "Initial goal"
    assert snapshot.questions == []
    assert snapshot.work_packages == [
        "follow-up: second",
        "follow-up: third",
        "follow-up: fourth",
    ]


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
