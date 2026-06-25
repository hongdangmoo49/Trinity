from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from trinity.textual_app.screens.execution_matrix import (
    ExecutionPackageRow,
    _PackageRowProjection,
)


class ExecutionPackageRowHarness(App[None]):
    def __init__(self, row: ExecutionPackageRow) -> None:
        super().__init__()
        self.row = row

    def compose(self) -> ComposeResult:
        yield self.row


@pytest.mark.asyncio
async def test_execution_package_row_status_change_updates_only_status_field() -> None:
    row = ExecutionPackageRow(
        package_id="WP-001",
        task="Build API",
        assignee="codex",
        executor="codex",
        status="running",
        review_status="pending",
        risk="low",
        button_id="detail-WP-001",
        button_label="Spec",
        task_width=28,
    )
    app = ExecutionPackageRowHarness(row)

    async with app.run_test(size=(100, 12)) as pilot:
        await pilot.pause()
        widgets = {
            "task": row.query_one(".execution-package-task", Static),
            "executor": row.query_one(".execution-package-executor", Static),
            "status": row.query_one(".execution-package-status", Static),
            "assignee": row.query_one(".execution-package-assignee", Static),
            "review": row.query_one(".execution-package-review", Static),
            "risk": row.query_one(".execution-package-risk", Static),
        }
        updates: dict[str, list[str]] = {key: [] for key in widgets}

        for key, widget in widgets.items():
            original_update = widget.update

            def counted_update(
                content,
                *,
                key=key,
                original_update=original_update,
            ) -> None:
                updates[key].append(str(content))
                original_update(content)

            widget.update = counted_update

        row.update_projection(
            _PackageRowProjection(
                identity="WP-001",
                package_id="WP-001",
                task="Build API",
                assignee="codex",
                executor="codex",
                status="done",
                review_status="pending",
                risk="low",
                button_id="detail-WP-001",
                button_label="Spec",
                task_width=28,
            )
        )
        await pilot.pause()

        assert updates == {
            "task": [],
            "executor": [],
            "status": ["done"],
            "assignee": [],
            "review": [],
            "risk": [],
        }
