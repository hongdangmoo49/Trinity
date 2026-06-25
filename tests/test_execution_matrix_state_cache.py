from __future__ import annotations

import pytest
from textual.app import App
from textual.containers import Vertical

from trinity.textual_app.screens.execution_matrix import ExecutionMatrixScreen
from trinity.textual_app.snapshot import WorkPackageSnapshot, WorkflowNexusSnapshot


class ExecutionHarness(App[None]):
    def __init__(self, screen: ExecutionMatrixScreen) -> None:
        super().__init__()
        self.execution = screen

    def on_mount(self) -> None:
        self.push_screen(self.execution)


def _snapshot() -> WorkflowNexusSnapshot:
    return WorkflowNexusSnapshot(
        session_id="wf-execution-cache",
        state="executing",
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Build API",
                owner_agent="codex",
                status="running",
                current_executor="codex",
            )
        ],
        execution_log=["event-1"],
    )


@pytest.mark.asyncio
async def test_execution_matrix_reuses_composed_fixed_widgets() -> None:
    screen = ExecutionMatrixScreen()
    app = ExecutionHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        query_calls: list[str] = []
        original_query_one = screen.query_one

        def counted_query_one(selector, *args, **kwargs):
            fixed_selectors = {
                "#execution-screen",
                "#execution-header",
                "#execution-summary",
                "#toggle-task-expanded",
                "#toggle-activity-expanded",
                "#execution-retry",
                "#execution-package-list",
                "#execution-log",
            }
            if selector in fixed_selectors:
                query_calls.append(selector)
            return original_query_one(selector, *args, **kwargs)

        screen.query_one = counted_query_one

        screen.apply_execution_state(None, _snapshot())
        await pilot.pause()
        screen.append_log("runtime-only-line")
        screen.action_toggle_task_expanded()
        await pilot.pause()
        screen.apply_execution_state(
            None,
            WorkflowNexusSnapshot(
                session_id="wf-execution-cache",
                state="executing",
                work_package_details=[
                    WorkPackageSnapshot(
                        id="WP-001",
                        title="Build API",
                        owner_agent="codex",
                        status="done",
                        current_executor="codex",
                    )
                ],
                execution_log=["event-1", "event-2"],
            ),
        )
        await pilot.pause()

        assert query_calls == []


@pytest.mark.asyncio
async def test_execution_matrix_skips_same_state_object_reapply() -> None:
    screen = ExecutionMatrixScreen()
    snapshot = _snapshot()
    app = ExecutionHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        screen.apply_execution_state(None, snapshot)
        await pilot.pause()

        calls: list[str] = []

        def counted_chrome() -> None:
            calls.append("chrome")

        def counted_packages() -> None:
            calls.append("packages")

        def counted_log() -> None:
            calls.append("log")

        screen._render_chrome = counted_chrome
        screen._render_package_list = counted_packages
        screen._render_log = counted_log

        screen.apply_execution_state(None, snapshot)
        await pilot.pause()
        assert calls == []

        screen.apply_execution_state(None, _snapshot())
        await pilot.pause()
        assert calls == ["chrome", "packages", "log"]


@pytest.mark.asyncio
async def test_execution_matrix_append_log_invalidates_state_identity_cache() -> None:
    screen = ExecutionMatrixScreen()
    snapshot = _snapshot()
    app = ExecutionHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        screen.apply_execution_state(None, snapshot)
        await pilot.pause()

        calls: list[str] = []

        def counted_log() -> None:
            calls.append("log")

        screen._render_log = counted_log
        screen.append_log("runtime-only-line")
        screen.apply_execution_state(None, snapshot)
        await pilot.pause()

        assert calls == ["log"]


@pytest.mark.asyncio
async def test_execution_matrix_skips_unchanged_task_expanded_class_sync() -> None:
    screen = ExecutionMatrixScreen()
    app = ExecutionHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()

        shell = screen.query_one("#execution-screen", Vertical)
        class_calls: list[bool] = []
        original_set_class = shell.set_class

        def counted_set_class(add: bool, class_name: str) -> None:
            if class_name == "execution-task-expanded":
                class_calls.append(add)
            original_set_class(add, class_name)

        shell.set_class = counted_set_class

        screen._sync_task_expanded_view()
        await pilot.pause()
        assert class_calls == [False]

        class_calls.clear()
        screen._sync_task_expanded_view()
        await pilot.pause()
        assert class_calls == []

        screen.tasks_expanded = True
        screen._sync_task_expanded_view()
        await pilot.pause()
        assert class_calls == [True]

        screen._sync_task_expanded_view()
        await pilot.pause()
        assert class_calls == [True]
