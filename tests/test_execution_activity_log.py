from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import RichLog

from trinity.textual_app.screens.execution_matrix import ExecutionMatrixScreen
from trinity.textual_app.snapshot import WorkflowNexusSnapshot


class ExecutionMatrixHarness(App[None]):
    def __init__(self, screen: ExecutionMatrixScreen) -> None:
        super().__init__()
        self.target_screen = screen

    def on_mount(self) -> None:
        self.push_screen(self.target_screen)


@pytest.mark.asyncio
async def test_execution_activity_log_appends_prefix_updates_without_clear() -> None:
    screen = ExecutionMatrixScreen()
    app = ExecutionMatrixHarness(screen)

    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(execution_log=["event-1"]),
        )
        await pilot.pause()
        log = screen.query_one("#execution-log", RichLog)
        writes: list[str] = []
        clears: list[bool] = []
        original_write = log.write
        original_clear = log.clear

        def counted_write(content, *args, **kwargs) -> None:
            writes.append(str(content))
            original_write(content, *args, **kwargs)

        def counted_clear() -> None:
            clears.append(True)
            original_clear()

        log.write = counted_write
        log.clear = counted_clear

        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(execution_log=["event-1", "event-2"]),
        )
        await pilot.pause()

        assert clears == []
        assert writes == ["event-2"]


@pytest.mark.asyncio
async def test_execution_activity_log_reconciles_direct_append_with_snapshot() -> None:
    screen = ExecutionMatrixScreen()
    app = ExecutionMatrixHarness(screen)

    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(execution_log=["event-1"]),
        )
        await pilot.pause()
        screen.append_log("runtime-only-line")
        await pilot.pause()

        log = screen.query_one("#execution-log", RichLog)
        writes: list[str] = []
        clears: list[bool] = []
        original_write = log.write
        original_clear = log.clear

        def counted_write(content, *args, **kwargs) -> None:
            writes.append(str(content))
            original_write(content, *args, **kwargs)

        def counted_clear() -> None:
            clears.append(True)
            original_clear()

        log.write = counted_write
        log.clear = counted_clear

        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(execution_log=["event-1"]),
        )
        await pilot.pause()

        assert clears == [True]
        assert writes == ["Activity", "event-1"]


@pytest.mark.asyncio
async def test_execution_activity_log_skips_reconcile_when_snapshot_catches_append() -> None:
    screen = ExecutionMatrixScreen()
    app = ExecutionMatrixHarness(screen)

    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(execution_log=["event-1"]),
        )
        await pilot.pause()
        screen.append_log("event-2")
        await pilot.pause()

        log = screen.query_one("#execution-log", RichLog)
        writes: list[str] = []
        clears: list[bool] = []
        original_write = log.write
        original_clear = log.clear

        def counted_write(content, *args, **kwargs) -> None:
            writes.append(str(content))
            original_write(content, *args, **kwargs)

        def counted_clear() -> None:
            clears.append(True)
            original_clear()

        log.write = counted_write
        log.clear = counted_clear

        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(execution_log=["event-1", "event-2"]),
        )
        await pilot.pause()

        assert clears == []
        assert writes == []


@pytest.mark.asyncio
async def test_execution_activity_log_clears_when_recent_window_changes() -> None:
    screen = ExecutionMatrixScreen()
    app = ExecutionMatrixHarness(screen)

    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(
                execution_log=[f"event-{index}" for index in range(1, 8)]
            ),
        )
        await pilot.pause()
        log = screen.query_one("#execution-log", RichLog)
        clears: list[bool] = []
        original_clear = log.clear

        def counted_clear() -> None:
            clears.append(True)
            original_clear()

        log.clear = counted_clear

        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(
                execution_log=[f"event-{index}" for index in range(1, 9)]
            ),
        )
        await pilot.pause()

        assert clears == [True]
