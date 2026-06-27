from trinity.textual_app.review_commands import (
    review_repair_action,
    review_matrix_notification_presentation,
    review_repair_blocked_package_ids,
    review_repair_snapshot,
    review_result_command_presentation,
    review_result_presentation,
)
from trinity.textual_app.snapshot import (
    ExecutionRecoverySnapshot,
    WorkflowNexusSnapshot,
    WorkPackageSnapshot,
)


def test_review_result_presentation_skips_empty_message() -> None:
    assert review_result_presentation(None) is None
    assert review_result_presentation("") is None


def test_review_result_presentation_warns_without_review_package() -> None:
    presentation = review_result_presentation("No review packages are ready.")

    assert presentation is not None
    assert presentation.message == "No review packages are ready."
    assert presentation.severity == "warning"


def test_review_result_presentation_warns_when_not_connected() -> None:
    presentation = review_result_presentation("Review provider is not connected.")

    assert presentation is not None
    assert presentation.severity == "warning"


def test_review_result_presentation_keeps_info_message() -> None:
    presentation = review_result_presentation("Review requested for WP-001.")

    assert presentation is not None
    assert presentation.severity == "info"


def test_review_result_command_presentation_builds_local_result() -> None:
    result = review_result_presentation("Review requested for WP-001.")
    assert result is not None
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-review",
        state="reviewing",
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Build feature",
                owner_agent="codex",
                status="done",
            )
        ],
    )

    presentation = review_result_command_presentation(result, snapshot)

    assert presentation.title == "Review"
    assert presentation.body == "Review requested for WP-001."
    assert presentation.severity == "info"
    assert presentation.table_columns == ("Item", "Value")
    assert ("Work Packages", "1") in presentation.table_rows
    assert ("Pending WP review", "WP-001") in presentation.table_rows
    assert presentation.action_hint == (
        "Run `/review wp`, `/review final`, or `/review all`."
    )


def test_review_matrix_notification_presentation_skips_empty_message() -> None:
    assert review_matrix_notification_presentation(None) is None
    assert review_matrix_notification_presentation("") is None


def test_review_matrix_notification_presentation_warns_when_no_pending() -> None:
    presentation = review_matrix_notification_presentation(
        "No pending work packages are ready for review."
    )

    assert presentation is not None
    assert presentation.body == "No pending work packages are ready for review."
    assert presentation.severity == "warning"


def test_review_matrix_notification_presentation_warns_for_workspace_message() -> None:
    presentation = review_matrix_notification_presentation(
        "Target workspace is required before review."
    )

    assert presentation is not None
    assert presentation.severity == "warning"


def test_review_matrix_notification_presentation_warns_when_still_running() -> None:
    presentation = review_matrix_notification_presentation(
        "Selected work package is still running."
    )

    assert presentation is not None
    assert presentation.severity == "warning"


def test_review_matrix_notification_presentation_keeps_info_message() -> None:
    presentation = review_matrix_notification_presentation(
        "Review requested for selected work packages.",
        lang="ko",
    )

    assert presentation is not None
    assert presentation.body == "Review requested for selected work packages."
    assert presentation.severity == "info"


def test_review_repair_blocked_package_ids_collects_package_and_recovery_ids() -> None:
    snapshot = WorkflowNexusSnapshot(
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-1",
                title="Build feature",
                owner_agent="codex",
                status="blocked",
                repair_blocked_reason="review changes required",
            )
        ],
        execution_recovery=ExecutionRecoverySnapshot(
            state="repair_blocked",
            retry_candidates=("WP-1", "WP-2"),
        ),
    )

    assert review_repair_blocked_package_ids(snapshot) == ("WP-1", "WP-2")


def test_review_repair_snapshot_builds_local_command_result() -> None:
    snapshot = WorkflowNexusSnapshot(
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-1",
                title="Build feature",
                owner_agent="codex",
                status="blocked",
                repair_blocked_reason="review changes required",
                review_status="changes_required",
                reviewer_agent="claude",
                review_summary="Need tests",
            )
        ],
        work_package_repairs=("Repair note",),
    )

    result = review_repair_snapshot("/review", snapshot)

    assert result.command == "/review"
    assert result.title == "Review Repair"
    assert result.severity == "warning"
    assert result.action_hint == (
        "Choose Retry once, Mark done, or Stop from the central panel."
    )
    assert result.table_columns == ("WP", "Repair state")
    assert result.table_rows[0][0] == "WP-1"
    assert "review changes required" in result.body
    assert "Repair note" in result.body


def test_review_repair_snapshot_supports_korean_title() -> None:
    result = review_repair_snapshot(
        "/review",
        WorkflowNexusSnapshot(),
        lang="ko",
    )

    assert result.title == "리뷰 보정"
    assert result.table_columns == ("작업 패키지", "보정 상태")


def test_review_repair_action_routes_known_actions() -> None:
    snapshot = WorkflowNexusSnapshot(
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-1",
                title="Build feature",
                owner_agent="codex",
                status="blocked",
                repair_blocked_reason="review changes required",
            )
        ],
        execution_recovery=ExecutionRecoverySnapshot(
            state="repair_blocked",
            retry_candidates=("WP-2",),
        ),
    )

    open_review = review_repair_action("repair-open-review", snapshot)
    retry_once = review_repair_action("repair-retry-once", snapshot)
    mark_done = review_repair_action("repair-mark-done", snapshot)
    stop = review_repair_action("repair-stop", snapshot)

    assert open_review.kind == "open_review"
    assert open_review.package_ids == ()
    assert retry_once.kind == "retry_once"
    assert retry_once.package_ids == ("WP-1", "WP-2")
    assert mark_done.kind == "mark_done"
    assert stop.kind == "stop"


def test_review_repair_action_ignores_unknown_action() -> None:
    action = review_repair_action("unknown", WorkflowNexusSnapshot())

    assert action.kind == "ignore"
    assert action.package_ids == ()
