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
