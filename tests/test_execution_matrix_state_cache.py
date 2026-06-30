from __future__ import annotations

import pytest
from textual.app import App
from textual.containers import Vertical
from textual.widgets import Button, RichLog

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
async def test_execution_matrix_skips_same_render_content_reapply() -> None:
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
        assert calls == []

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
        assert calls == ["chrome", "packages", "log"]


@pytest.mark.asyncio
async def test_execution_matrix_updates_row_action_buttons_without_list_rebuild() -> None:
    screen = ExecutionMatrixScreen()
    review_snapshot = WorkflowNexusSnapshot(
        session_id="wf-execution-cache",
        state="executing",
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Build API",
                owner_agent="codex",
                status="running",
                current_executor="codex",
                review_status="needs_second_review",
            )
        ],
        execution_log=["event-1"],
    )
    retry_review_snapshot = WorkflowNexusSnapshot(
        session_id="wf-execution-cache",
        state="executing",
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Build API",
                owner_agent="codex",
                status="failed",
                current_executor="codex",
                review_status="needs_second_review",
                retryable=True,
            )
        ],
        execution_log=["event-1", "event-2"],
    )
    plain_snapshot = WorkflowNexusSnapshot(
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
        execution_log=["event-1", "event-2", "event-3"],
    )
    app = ExecutionHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        screen.apply_execution_state(None, review_snapshot)
        await pilot.pause()

        package_list = screen.package_list()
        rebuilds: list[bool] = []
        original_remove_children = package_list.remove_children

        def counted_remove_children(*args, **kwargs):
            rebuilds.append(True)
            return original_remove_children(*args, **kwargs)

        package_list.remove_children = counted_remove_children

        screen.apply_execution_state(None, retry_review_snapshot)
        await pilot.pause()

        assert rebuilds == []
        retry_button = screen.query_one("#wp-retry-0", Button)
        assert retry_button.name == "WP-001"
        action_ids = [
            button.id
            for button in screen.query(".execution-package-actions Button")
        ]
        assert action_ids == ["wp-detail-0", "wp-retry-0", "wp-review-0"]

        screen.apply_execution_state(None, plain_snapshot)
        await pilot.pause()

        assert rebuilds == []
        assert not list(screen.query("#wp-retry-0"))
        assert not list(screen.query("#wp-review-0"))


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

        screen.sync_task_expanded_view()
        await pilot.pause()
        assert class_calls == [False]

        class_calls.clear()
        screen.sync_task_expanded_view()
        await pilot.pause()
        assert class_calls == []

        screen.tasks_expanded = True
        screen.sync_task_expanded_view()
        await pilot.pause()
        assert class_calls == [True]

        screen.sync_task_expanded_view()
        await pilot.pause()
        assert class_calls == [True]


@pytest.mark.asyncio
async def test_execution_matrix_recompose_resets_render_identity_caches() -> None:
    screen = ExecutionMatrixScreen()
    snapshot = _snapshot()
    app = ExecutionHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        screen.apply_execution_state(None, snapshot)
        await pilot.pause()

        first_summary = screen._summary_widget
        first_package_list = screen._package_list_widget
        first_log = screen._log_widget
        assert screen._applied_state_identity == (None, id(snapshot))
        assert screen._render_content_key is not None
        assert screen._chrome_render_key is not None
        assert screen._package_list_identity is not None
        assert screen._activity_lines_key

        screen.refresh(recompose=True)
        await pilot.pause()

        assert screen._summary_widget is not first_summary
        assert screen._package_list_widget is not first_package_list
        assert screen._log_widget is not first_log
        assert screen._applied_state_identity is None
        assert screen._chrome_render_key is None
        assert screen._chrome_projection_cache is None
        assert screen._render_content_key is None
        assert screen._package_list_identity is None
        assert screen._package_row_keys == {}
        assert screen._package_rows == {}
        assert screen._activity_lines_key == ()
        assert screen._task_expanded_view_key is None

        query_calls: list[str] = []
        original_query_one = screen.query_one

        def counted_query_one(selector, *args, **kwargs):
            if str(selector).startswith("#execution"):
                query_calls.append(str(selector))
            return original_query_one(selector, *args, **kwargs)

        screen.query_one = counted_query_one
        log = screen._log_widget
        assert isinstance(log, RichLog)
        writes: list[str] = []
        original_write = log.write

        def counted_write(content, *args, **kwargs) -> None:
            writes.append(str(content))
            original_write(content, *args, **kwargs)

        log.write = counted_write

        screen.apply_execution_state(None, snapshot)
        await pilot.pause()

        assert query_calls == []
        assert "RUN" in str(screen._summary_widget.content)
        assert screen._package_list_widget is not None
        assert len(screen._package_list_widget.children) >= 2
        assert writes[-2:] == ["Activity", "event-1"]
        assert screen._applied_state_identity == (None, id(snapshot))
