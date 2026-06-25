from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from trinity.textual_app.snapshot import WorkPackageSnapshot, WorkflowNexusSnapshot
from trinity.textual_app.widgets.inspector import WorkflowInspector


class InspectorHarness(App[None]):
    def __init__(self, inspector: WorkflowInspector) -> None:
        super().__init__()
        self.inspector = inspector

    def compose(self) -> ComposeResult:
        yield self.inspector


def _snapshot(*, status: str) -> WorkflowNexusSnapshot:
    return WorkflowNexusSnapshot(
        session_id="wf-inspector-cache",
        state="executing",
        round_num=1,
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Build API",
                owner_agent="codex",
                status=status,
                current_executor="codex" if status == "running" else "",
            )
        ],
        execution_log=["event-1"],
    )


@pytest.mark.asyncio
async def test_workflow_inspector_reuses_composed_section_widgets() -> None:
    inspector = WorkflowInspector()
    app = InspectorHarness(inspector)

    async with app.run_test(size=(100, 28)) as pilot:
        await pilot.pause()
        query_calls: list[str] = []
        original_query_one = inspector.query_one

        def counted_query_one(selector, *args, **kwargs):
            if isinstance(selector, str) and selector.startswith("#inspector-"):
                query_calls.append(selector)
            return original_query_one(selector, *args, **kwargs)

        inspector.query_one = counted_query_one

        inspector.apply_snapshot(_snapshot(status="running"))
        await pilot.pause()
        inspector.apply_snapshot(_snapshot(status="done"))
        await pilot.pause()

        assert query_calls == []


@pytest.mark.asyncio
async def test_workflow_inspector_skips_unchanged_projection_calculation() -> None:
    inspector = WorkflowInspector()
    app = InspectorHarness(inspector)

    async with app.run_test(size=(100, 28)) as pilot:
        inspector.apply_snapshot(_snapshot(status="running"))
        await pilot.pause()

        progress_calls: list[bool] = []
        original_progress = inspector._progress_summary

        def counted_progress(snapshot) -> str:
            progress_calls.append(True)
            return original_progress(snapshot)

        inspector._progress_summary = counted_progress

        inspector.apply_snapshot(_snapshot(status="running"))
        await pilot.pause()
        assert progress_calls == []

        inspector.apply_snapshot(_snapshot(status="done"))
        await pilot.pause()
        assert progress_calls == [True]


@pytest.mark.asyncio
async def test_workflow_inspector_rebinds_render_keys_after_recompose() -> None:
    inspector = WorkflowInspector()
    snapshot = _snapshot(status="running")
    app = InspectorHarness(inspector)

    async with app.run_test(size=(100, 28)) as pilot:
        inspector.apply_snapshot(snapshot)
        await pilot.pause()

        assert "wf-inspector-cache" in str(
            inspector.query_one("#inspector-workflow").content
        )
        assert "WP-001" in str(inspector.query_one("#inspector-current").content)

        inspector.refresh(recompose=True)
        await pilot.pause()

        assert str(inspector.query_one("#inspector-workflow").content) == ""
        assert str(inspector.query_one("#inspector-current").content) == ""

        inspector.apply_snapshot(snapshot)
        await pilot.pause()

        assert "wf-inspector-cache" in str(
            inspector.query_one("#inspector-workflow").content
        )
        assert "WP-001" in str(inspector.query_one("#inspector-current").content)
