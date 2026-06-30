from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from trinity.textual_app.widgets.project_brief_modal import (
    ProjectBriefDraft,
    ProjectBriefModal,
)


@pytest.mark.asyncio
async def test_project_brief_modal_keeps_actions_inside_narrow_viewport() -> None:
    draft = ProjectBriefDraft(
        product_goal="Build a detailed planning application " * 6,
        project_type="Textual application with local persistence",
        starter_profile="Textual TUI with SQLite and report export",
        target_users="operators, reviewers, release managers",
        success_criteria="Users can plan, execute, review, and recover work " * 4,
        stack_preferences=("python", "textual", "sqlite", "rich", "pytest"),
        first_milestone="First end-to-end workflow " * 5,
        run_commands=("uv run trinity-demo --workspace ./very-long-target",),
        validation_commands=("uv run pytest " + "tests/test_long_name.py " * 8,),
        artifact_targets=("README.md", "src/app", "tests", "docs/plans"),
        constraints=("offline first", "no external service", "small terminal friendly"),
        notes="Keep the generated plan concise and implementation-ready. " * 6,
    )

    class ProbeApp(App[None]):
        def compose(self) -> ComposeResult:
            yield Static("root")

        def on_mount(self) -> None:
            self.push_screen(
                ProjectBriefModal(
                    draft,
                    lang="en",
                    target_workspace="/workspace/" + "long-target-directory-" * 5,
                    mode="new",
                )
            )

    app = ProbeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        modal = app.screen
        shell = modal.query_one("#project-brief-modal")

        for widget_id in (
            "#project-brief-title",
            "#project-brief-content",
            "#project-brief-actions",
            "#cancel-project-brief",
            "#save-project-brief",
        ):
            widget = modal.query_one(widget_id)
            assert widget.region.y >= shell.region.y
            assert widget.region.y + widget.region.height <= (
                shell.region.y + shell.region.height
            )
