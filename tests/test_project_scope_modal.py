from __future__ import annotations

from dataclasses import replace

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from trinity.project_intake import build_project_intake
from trinity.textual_app.widgets.project_scope_modal import ProjectScopeModal


@pytest.mark.asyncio
async def test_project_scope_modal_keeps_actions_inside_narrow_viewport(
    tmp_path,
) -> None:
    workspace = tmp_path / ("long-target-directory-" * 5)
    workspace.mkdir()
    intake = replace(
        build_project_intake(mode="existing", target_workspace=workspace),
        scope_candidates=tuple(
            f"apps/feature-{index}-with-a-long-scope-name" for index in range(12)
        ),
        selected_scope="apps/feature-0-with-a-long-scope-name",
    )

    class ProbeApp(App[None]):
        def compose(self) -> ComposeResult:
            yield Static("root")

        def on_mount(self) -> None:
            self.push_screen(ProjectScopeModal(intake, lang="en"))

    app = ProbeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        modal = app.screen
        shell = modal.query_one("#project-scope-modal")

        for widget_id in (
            "#project-scope-title",
            "#project-scope-content",
            "#project-scope-actions",
            "#cancel-project-scope",
            "#save-project-scope",
        ):
            widget = modal.query_one(widget_id)
            assert widget.region.y >= shell.region.y
            assert widget.region.y + widget.region.height <= (
                shell.region.y + shell.region.height
            )
