from __future__ import annotations

from types import SimpleNamespace

import pytest
from textual.app import App
from textual.widgets import Button, Input, RichLog, Static

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
async def test_execution_log_modal_reuses_composed_refresh_widgets() -> None:
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
        query_calls: list[str] = []
        original_query_one = modal.query_one

        def counted_query_one(selector, *args, **kwargs):
            if selector in {
                "#execution-log-search-status",
                "#execution-log-modal-body",
            }:
                query_calls.append(selector)
            return original_query_one(selector, *args, **kwargs)

        modal.query_one = counted_query_one

        modal.filter_query = "fail"
        modal._refresh_log()
        await pilot.pause()
        modal.filter_query = "complete"
        modal._refresh_log()
        await pilot.pause()

        assert query_calls == []


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


@pytest.mark.asyncio
async def test_execution_log_modal_skips_case_only_search_query() -> None:
    modal = ExecutionLogModal(["WP-001 failed", "WP-002 completed"])
    app = ExecutionLogModalHarness(modal)

    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        calls: list[str] = []
        modal.filter_query = "fail"

        def counted_refresh() -> None:
            calls.append(modal.filter_query)

        modal._refresh_log = counted_refresh

        modal.on_input_changed(_input_event(" FAIL "))
        assert calls == []
        assert modal.filter_query == "fail"

        modal.on_input_changed(_input_event("complete"))
        assert calls == ["complete"]
        assert modal.filter_query == "complete"


@pytest.mark.asyncio
async def test_execution_log_modal_recompose_rebinds_render_keys() -> None:
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
        modal.filter_query = "failed"
        modal._refresh_log()
        await pilot.pause()

        first_status = modal._status_widget
        first_body = modal._body_widget
        assert modal._status_text_key
        assert modal._rendered_lines_key

        modal.refresh(recompose=True)
        await pilot.pause()

        assert modal._status_widget is not first_status
        assert modal._body_widget is not first_body
        assert modal._status_text_key == ""
        assert modal._rendered_lines_key == ()
        assert modal.query_one("#execution-log-search", Input).value == "failed"

        query_calls: list[str] = []
        original_query_one = modal.query_one

        def counted_query_one(selector, *args, **kwargs):
            if selector in {
                "#execution-log-search-status",
                "#execution-log-modal-body",
            }:
                query_calls.append(str(selector))
            return original_query_one(selector, *args, **kwargs)

        modal.query_one = counted_query_one
        status = modal._status_widget
        body = modal._body_widget
        assert isinstance(status, Static)
        assert isinstance(body, RichLog)
        status_updates: list[str] = []
        writes: list[str] = []
        original_status_update = status.update
        original_write = body.write

        def counted_status_update(content) -> None:
            status_updates.append(str(content))
            original_status_update(content)

        def counted_write(content, *args, **kwargs) -> None:
            writes.append(str(content))
            original_write(content, *args, **kwargs)

        status.update = counted_status_update
        body.write = counted_write

        modal._refresh_log()
        await pilot.pause()

        assert query_calls == []
        assert status_updates == ["Showing 1 of 1 matches"]
        assert writes
        assert set(writes) == {"WP-002 failed with provider error"}


@pytest.mark.asyncio
async def test_execution_log_modal_keeps_controls_inside_narrow_viewport() -> None:
    modal = ExecutionLogModal(
        [
            f"WP-{index:03d} produced a very long execution log line with details"
            for index in range(700)
        ]
    )
    app = ExecutionLogModalHarness(modal)

    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        shell = modal.query_one("#execution-log-modal")

        for widget_id in (
            "#execution-log-modal-title",
            "#execution-log-search",
            "#execution-log-search-status",
            "#execution-log-modal-body",
            "#close-execution-log",
        ):
            widget = modal.query_one(widget_id)
            assert widget.region.y >= shell.region.y
            assert widget.region.y + widget.region.height <= (
                shell.region.y + shell.region.height
            )
        assert str(modal.query_one("#close-execution-log", Button).label) == "Close"
