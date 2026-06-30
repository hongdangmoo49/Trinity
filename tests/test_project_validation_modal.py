from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from trinity.project_intake import build_project_intake
from trinity.textual_app.widgets.project_validation_modal import ProjectValidationModal


@pytest.mark.asyncio
async def test_project_validation_modal_keeps_actions_inside_narrow_viewport(
    tmp_path,
) -> None:
    workspace = tmp_path / ("long-target-directory-" * 5)
    workspace.mkdir()
    intake = build_project_intake(
        mode="new",
        target_workspace=workspace,
        product_goal="Build a planning board.",
        project_type="textual app",
        target_users="operators",
        success_criteria="Operators can plan weekly work.",
        stack_preferences=("python", "textual", "sqlite", "rich"),
        first_milestone="First board workflow.",
        validation_commands=("uv run pytest " + "tests/test_long_name.py " * 8,),
        run_commands=("uv run trinity-demo --workspace " + str(workspace),),
        constraints=("No external service " * 10,),
    )

    class ProbeApp(App[None]):
        def compose(self) -> ComposeResult:
            yield Static("root")

        def on_mount(self) -> None:
            self.push_screen(ProjectValidationModal(intake, lang="en"))

    app = ProbeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        modal = app.screen
        shell = modal.query_one("#project-validation-modal")

        for widget_id in (
            "#project-validation-title",
            "#project-validation-content",
            "#project-validation-actions",
            "#cancel-project-validation",
            "#save-project-validation",
        ):
            widget = modal.query_one(widget_id)
            assert widget.region.y >= shell.region.y
            assert widget.region.y + widget.region.height <= (
                shell.region.y + shell.region.height
            )
