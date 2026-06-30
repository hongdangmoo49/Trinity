from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from trinity.textual_app.widgets.target_workspace_confirm_modal import (
    TargetWorkspaceConfirmModal,
)


@pytest.mark.asyncio
async def test_target_workspace_confirm_modal_keeps_actions_inside_narrow_viewport() -> None:
    target_path = Path("/workspace") / ("very-long-target-directory-" * 8)
    control_repo = target_path / ("nested-control-repository-directory-" * 6)

    class ProbeApp(App[None]):
        def compose(self) -> ComposeResult:
            yield Static("root")

        def on_mount(self) -> None:
            self.push_screen(
                TargetWorkspaceConfirmModal(
                    target_path=target_path,
                    control_repo=control_repo,
                    lang="en",
                )
            )

    app = ProbeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        modal = app.screen
        shell = modal.query_one("#target-confirm-modal")

        for widget_id in (
            "#target-confirm-title",
            "#target-confirm-content",
            "#target-confirm-actions",
            "#cancel-target-confirm",
            "#confirm-target",
        ):
            widget = modal.query_one(widget_id)
            assert widget.region.y >= shell.region.y
            assert widget.region.y + widget.region.height <= (
                shell.region.y + shell.region.height
            )
