from trinity.textual_app.review_commands import (
    review_matrix_notification_presentation,
    review_result_command_presentation,
    review_result_presentation,
)
from trinity.textual_app.snapshot import WorkflowNexusSnapshot, WorkPackageSnapshot


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
