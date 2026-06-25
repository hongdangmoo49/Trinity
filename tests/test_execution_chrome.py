from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import Static

from trinity.textual_app.screens.execution_matrix import (
    ExecutionMatrixScreen,
    _ChromeProjection,
)


class ExecutionMatrixHarness(App[None]):
    def __init__(self, screen: ExecutionMatrixScreen) -> None:
        super().__init__()
        self.target_screen = screen

    def on_mount(self) -> None:
        self.push_screen(self.target_screen)


@pytest.mark.asyncio
async def test_execution_chrome_summary_change_updates_only_summary() -> None:
    screen = ExecutionMatrixScreen()
    app = ExecutionMatrixHarness(screen)

    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        screen._chrome_projection = lambda: _ChromeProjection(
            header_text="Execution: ready",
            summary_text="1 package ready",
            task_toggle_label="Expand Tasks",
            activity_toggle_label="Full Log",
            retry_label="Retry",
            retry_disabled=True,
        )
        screen._render_chrome()
        await pilot.pause()

        header = screen.query_one("#execution-header", Static)
        summary = screen.query_one("#execution-summary", Static)
        updates: dict[str, list[str]] = {"header": [], "summary": []}
        original_header_update = header.update
        original_summary_update = summary.update

        def counted_header_update(content) -> None:
            updates["header"].append(str(content))
            original_header_update(content)

        def counted_summary_update(content) -> None:
            updates["summary"].append(str(content))
            original_summary_update(content)

        header.update = counted_header_update
        summary.update = counted_summary_update
        screen._chrome_projection = lambda: _ChromeProjection(
            header_text="Execution: ready",
            summary_text="1 package done",
            task_toggle_label="Expand Tasks",
            activity_toggle_label="Full Log",
            retry_label="Retry",
            retry_disabled=True,
        )

        screen._render_chrome()
        await pilot.pause()

        assert updates == {
            "header": [],
            "summary": ["1 package done"],
        }
