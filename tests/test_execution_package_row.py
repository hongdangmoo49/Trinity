from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, Static

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

        child_queries: list[str] = []
        original_query_one = row.query_one
        original_query = row.query

        def counted_query_one(selector, *args, **kwargs):
            if str(selector).startswith(".execution-package-"):
                child_queries.append(str(selector))
            return original_query_one(selector, *args, **kwargs)

        def counted_query(selector, *args, **kwargs):
            if selector in {
                ".execution-package-retry",
                ".execution-package-review-action",
            }:
                child_queries.append(str(selector))
            return original_query(selector, *args, **kwargs)

        row.query_one = counted_query_one
        row.query = counted_query

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
        assert child_queries == []


@pytest.mark.asyncio
async def test_execution_package_row_detail_button_updates_when_projection_changes() -> None:
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
        queries: list[str] = []
        original_query_one = row.query_one

        def counted_query_one(selector, *args, **kwargs):
            if selector == ".execution-package-spec":
                queries.append(str(selector))
            return original_query_one(selector, *args, **kwargs)

        row.query_one = counted_query_one

        row.update_projection(
            _PackageRowProjection(
                identity="WP-001",
                package_id="WP-001",
                task="Build API",
                assignee="codex",
                executor="codex",
                status="running",
                review_status="pending",
                risk="low",
                button_id="detail-WP-001",
                button_label="Details",
                task_width=28,
                detail_enabled=False,
            )
        )
        await pilot.pause()

        assert queries == []
        button = row._button_cache[".execution-package-spec"]
        assert str(button.label) == "Details"
        assert button.disabled is True


@pytest.mark.asyncio
async def test_execution_package_row_recompose_rebinds_cached_widgets() -> None:
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
        first_status = row._static_cache[".execution-package-status"]
        first_detail = row._button_cache[".execution-package-spec"]

        row.refresh(recompose=True)
        await pilot.pause()

        assert row._static_cache[".execution-package-status"] is not first_status
        assert row._button_cache[".execution-package-spec"] is not first_detail

        query_calls: list[str] = []
        original_query_one = row.query_one

        def counted_query_one(selector, *args, **kwargs):
            if str(selector).startswith(".execution-package-"):
                query_calls.append(str(selector))
            return original_query_one(selector, *args, **kwargs)

        row.query_one = counted_query_one

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
                button_label="Details",
                task_width=28,
                detail_enabled=False,
            )
        )
        await pilot.pause()

        assert query_calls == []
        status = row._static_cache[".execution-package-status"]
        detail = row._button_cache[".execution-package-spec"]
        assert isinstance(status, Static)
        assert str(status.content) == "done"
        assert isinstance(detail, Button)
        assert str(detail.label) == "Details"
        assert detail.disabled is True
