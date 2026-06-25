from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import Button, Static

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
