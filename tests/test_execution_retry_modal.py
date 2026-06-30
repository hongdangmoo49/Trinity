from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import Button, Static

from trinity.config import TrinityConfig
from trinity.textual_app.app import TrinityTextualApp
from trinity.textual_app.snapshot import WorkPackageSnapshot, WorkflowNexusSnapshot
from trinity.textual_app.widgets.execution_retry_modal import ExecutionRetryModal


class ExecutionRetryModalHarness(App[None]):
    def __init__(self, modal: ExecutionRetryModal) -> None:
        super().__init__()
        self.modal = modal

    def on_mount(self) -> None:
        self.push_screen(self.modal)


def _retry_snapshot() -> WorkflowNexusSnapshot:
    return WorkflowNexusSnapshot(
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Build API",
                owner_agent="codex",
                status="failed",
                retryable=True,
            ),
            WorkPackageSnapshot(
                id="WP-002",
                title="Build UI",
                owner_agent="claude",
                status="blocked",
                retryable=True,
            ),
        ]
    )


@pytest.mark.asyncio
async def test_execution_retry_modal_reuses_cached_state_widgets() -> None:
    modal = ExecutionRetryModal(_retry_snapshot())
    app = ExecutionRetryModalHarness(modal)

    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        query_calls: list[str] = []
        original_query_one = modal.query_one

        def counted_query_one(selector, *args, **kwargs):
            if selector in {
                "#execution-retry-selected",
                "#confirm-execute-retry",
            }:
                query_calls.append(selector)
            return original_query_one(selector, *args, **kwargs)

        modal.query_one = counted_query_one

        modal.selected_ids.clear()
        modal._refresh_selection_state()
        modal.selected_ids = {"WP-001"}
        modal._refresh_selection_state()
        await pilot.pause()

        assert query_calls == [
            "#execution-retry-selected",
            "#confirm-execute-retry",
        ]


@pytest.mark.asyncio
async def test_execution_retry_modal_skips_unchanged_selection_update() -> None:
    modal = ExecutionRetryModal(_retry_snapshot())
    app = ExecutionRetryModalHarness(modal)

    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        selected = modal.query_one("#execution-retry-selected", Static)
        updates: list[str] = []
        original_update = selected.update

        def counted_update(content) -> None:
            updates.append(str(content))
            original_update(content)

        selected.update = counted_update

        modal._refresh_selection_state()
        await pilot.pause()

        assert updates == []


@pytest.mark.asyncio
async def test_execution_retry_modal_updates_selection_when_state_changes() -> None:
    modal = ExecutionRetryModal(_retry_snapshot())
    app = ExecutionRetryModalHarness(modal)

    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        selected = modal.query_one("#execution-retry-selected", Static)
        confirm = modal.query_one("#confirm-execute-retry", Button)

        modal.selected_ids.clear()
        modal._refresh_selection_state()
        await pilot.pause()

        assert str(selected.content) == "Selected: (none)"
        assert confirm.disabled is True


@pytest.mark.asyncio
async def test_execution_retry_modal_skips_current_filter_recompose() -> None:
    modal = ExecutionRetryModal(_retry_snapshot())
    app = ExecutionRetryModalHarness(modal)

    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        recompose_calls: list[bool] = []
        original_refresh = modal.refresh

        def counted_refresh(*args, **kwargs) -> None:
            recompose_calls.append(bool(kwargs.get("recompose")))
            original_refresh(*args, **kwargs)

        modal.refresh = counted_refresh

        modal.query_one("#retry-filter-all", Button).press()
        await pilot.pause()
        assert True not in recompose_calls

        recompose_calls.clear()
        modal.query_one("#retry-filter-blocked", Button).press()
        await pilot.pause()
        assert recompose_calls[0] is True


@pytest.mark.asyncio
async def test_execution_retry_modal_keeps_actions_inside_narrow_viewport(
    tmp_path,
) -> None:
    snapshot = WorkflowNexusSnapshot(
        target_workspace="/workspace/" + "long-target-directory-" * 6,
        work_package_details=[
            WorkPackageSnapshot(
                id=f"WP-{index:03d}",
                title=f"Retryable package {index} with a long topic name",
                topic=f"Retryable package {index} with a long topic name",
                owner_agent="codex" if index % 2 else "claude",
                status=("failed", "blocked", "running")[index % 3],
                current_executor="codex",
                retryable=True,
            )
            for index in range(18)
        ],
    )
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(80, 24)) as pilot:
        app.push_screen(ExecutionRetryModal(snapshot, selector="custom", lang="en"))
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, ExecutionRetryModal)
        shell = modal.query_one("#execution-retry-modal")

        for widget_id in (
            "#execution-retry-title",
            "#execution-retry-summary",
            "#execution-retry-filters",
            "#execution-retry-list",
            "#execution-retry-selected",
            "#execution-retry-actions",
            "#cancel-execute-retry",
            "#confirm-execute-retry",
        ):
            widget = modal.query_one(widget_id)
            assert widget.region.y >= shell.region.y
            assert widget.region.y + widget.region.height <= (
                shell.region.y + shell.region.height
            )
