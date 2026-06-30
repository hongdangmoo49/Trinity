from __future__ import annotations

import pytest
from textual.widgets import Button

from trinity.config import TrinityConfig
from trinity.textual_app.app import TrinityTextualApp
from trinity.textual_app.snapshot import WorkPackageSnapshot
from trinity.textual_app.widgets.work_package_detail_modal import (
    WorkPackageDetailModal,
)


@pytest.mark.asyncio
async def test_work_package_detail_modal_keeps_close_inside_narrow_viewport(
    tmp_path,
) -> None:
    package = WorkPackageSnapshot(
        id="WP-999",
        title="Build " + "very long package title " * 10,
        topic="Execution detail topic " * 6,
        owner_agent="codex",
        status="failed",
        risk="high",
        current_executor="codex",
        objective="Improve execution detail presentation " * 8,
        scope=[f"scope item {index} with long details" for index in range(10)],
        out_of_scope=[f"out of scope {index}" for index in range(6)],
        dependencies=[f"WP-{index:03d}" for index in range(8)],
        expected_files=[
            f"src/module_{index}/very_long_file_name.py" for index in range(8)
        ],
        acceptance_criteria=[f"criterion {index} is verified" for index in range(8)],
        repair_notes=[f"repair note {index} with context" for index in range(6)],
        repair_attempt_count=2,
        repair_max_attempts=3,
        repair_blocked_reason="duplicate_required_changes",
        last_result_agent="codex",
        last_result_status="failed",
        last_result_summary="Could not complete the implementation " * 8,
        last_result_files_changed=[f"src/changed_{index}.py" for index in range(8)],
        last_result_blockers=[
            f"blocker {index} needs follow-up" for index in range(8)
        ],
        last_result_attempt_chain=[f"attempt-{index}" for index in range(6)],
        retryable=True,
        review_status="changes_requested",
        reviewer_agent="claude, antigravity",
        review_summary="Review found several issues " * 6,
        review_required_changes=[f"required change {index}" for index in range(8)],
        review_severity="medium",
        task_kind="implementation",
        routing_reason="implementation strength and recent success",
        routing_score=98.0,
        profile_revision="default-v1",
    )
    app = TrinityTextualApp(TrinityConfig.default_config(project_dir=tmp_path))

    async with app.run_test(size=(80, 24)) as pilot:
        app.push_screen(WorkPackageDetailModal(package, lang="en"))
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, WorkPackageDetailModal)
        shell = modal.query_one("#work-package-detail-modal")

        for widget_id in (
            "#work-package-detail-title",
            "#work-package-detail-body",
            "#close-work-package-detail",
        ):
            widget = modal.query_one(widget_id)
            assert widget.region.y >= shell.region.y
            assert widget.region.y + widget.region.height <= (
                shell.region.y + shell.region.height
            )
        assert str(modal.query_one("#close-work-package-detail", Button).label) == (
            "Close"
        )
