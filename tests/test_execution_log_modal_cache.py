from __future__ import annotations

from types import SimpleNamespace

import pytest
from textual.app import App
from textual.widgets import RichLog, Static

from trinity.textual_app.widgets.execution_log_modal import ExecutionLogModal


class ExecutionLogModalHarness(App[None]):
    def __init__(self, modal: ExecutionLogModal) -> None:
        super().__init__()
        self.modal = modal

    def on_mount(self) -> None:
        self.push_screen(self.modal)


def _input_event(value: str, *, input_id: str = "execution-log-search"):
    return SimpleNamespace(input=SimpleNamespace(id=input_id), value=value)


@pytest.mark.asyncio
async def test_execution_log_modal_skips_unchanged_render_state() -> None:
    modal = ExecutionLogModal(
        [
            "WP-001 started",
            "WP-002 failed with provider error",
            "WP-003 completed",
        ]
    )
    app = ExecutionLogModalHarness(modal)

    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        modal.filter_query = "fail"
        modal._refresh_log()
        await pilot.pause()

        status = modal.query_one("#execution-log-search-status", Static)
        body = modal.query_one("#execution-log-modal-body", RichLog)
        status_updates: list[str] = []
        clears: list[bool] = []
        writes: list[str] = []
        original_status_update = status.update
        original_clear = body.clear
        original_write = body.write

        def counted_status_update(content) -> None:
            status_updates.append(str(content))
            original_status_update(content)

        def counted_clear() -> None:
            clears.append(True)
            original_clear()

        def counted_write(content, *args, **kwargs) -> None:
            writes.append(str(content))
            original_write(content, *args, **kwargs)

        status.update = counted_status_update
        body.clear = counted_clear
        body.write = counted_write

        modal.filter_query = "fail"
        modal._refresh_log()
        await pilot.pause()

        assert status_updates == []
        assert clears == []
        assert writes == []


@pytest.mark.asyncio
async def test_execution_log_modal_skips_unchanged_search_query() -> None:
    modal = ExecutionLogModal(["WP-001 failed", "WP-002 completed"])
    app = ExecutionLogModalHarness(modal)

    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        calls: list[str] = []
        modal.filter_query = "fail"

        def counted_refresh() -> None:
            calls.append(modal.filter_query)

        modal._refresh_log = counted_refresh

        modal.on_input_changed(_input_event(" fail "))
        assert calls == []
        assert modal.filter_query == "fail"

        modal.on_input_changed(_input_event("complete"))
        assert calls == ["complete"]
        assert modal.filter_query == "complete"
