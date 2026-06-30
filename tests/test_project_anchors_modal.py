from __future__ import annotations

from dataclasses import replace

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from trinity.project_intake import build_project_intake
from trinity.textual_app.widgets.project_anchors_modal import ProjectAnchorsModal


@pytest.mark.asyncio
async def test_project_anchors_modal_keeps_actions_inside_narrow_viewport(
    tmp_path,
) -> None:
    workspace = tmp_path / ("long-target-directory-" * 5)
    workspace.mkdir()
    intake = replace(
        build_project_intake(mode="existing", target_workspace=workspace),
        docs_found=tuple(f"docs/guide-{index}-with-a-long-name.md" for index in range(8)),
        source_roots=tuple(f"packages/module-{index}/src" for index in range(8)),
        scope_candidates=tuple(
            f"packages/module-{index}-with-a-long-scope-name" for index in range(10)
        ),
        selected_scope="packages/module-0-with-a-long-scope-name",
        test_commands=("uv run pytest " + "tests/test_long_name.py " * 8,),
        dev_commands=("uv run textual dev --target " + str(workspace),),
        build_commands=("uv build --out-dir " + str(workspace / "dist"),),
    )

    class ProbeApp(App[None]):
        def compose(self) -> ComposeResult:
            yield Static("root")

        def on_mount(self) -> None:
            self.push_screen(ProjectAnchorsModal(intake, lang="en"))

    app = ProbeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        modal = app.screen
        shell = modal.query_one("#project-anchors-modal")

        for widget_id in (
            "#project-anchors-title",
            "#project-anchors-content",
            "#project-anchors-actions",
            "#cancel-project-anchors",
            "#save-project-anchors",
        ):
            widget = modal.query_one(widget_id)
            assert widget.region.y >= shell.region.y
            assert widget.region.y + widget.region.height <= (
                shell.region.y + shell.region.height
            )
