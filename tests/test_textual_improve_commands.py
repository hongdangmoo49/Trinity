from trinity.textual_app.improve_commands import (
    improve_command_effect,
    improve_result_command_presentation,
    improve_result_presentation,
)
from trinity.textual_app.snapshot import (
    PostReviewActionSnapshot,
    WorkflowNexusSnapshot,
)


def test_improve_result_presentation_skips_empty_message() -> None:
    assert improve_result_presentation(None) is None
    assert improve_result_presentation("") is None


def test_improve_result_presentation_warns_without_matching_item() -> None:
    presentation = improve_result_presentation("No matching post-review item.")

    assert presentation is not None
    assert presentation.message == "No matching post-review item."
    assert presentation.severity == "warning"


def test_improve_result_presentation_warns_when_required() -> None:
    presentation = improve_result_presentation("Target workspace is required.")

    assert presentation is not None
    assert presentation.severity == "warning"


def test_improve_result_presentation_keeps_info_message() -> None:
    presentation = improve_result_presentation("Queued supplemental work.")

    assert presentation is not None
    assert presentation.severity == "info"


def test_improve_result_command_presentation_builds_local_result() -> None:
    result = improve_result_presentation("Queued supplemental work.")
    assert result is not None
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-improve",
        state="improving",
        supplemental_round=1,
        post_review_items=[
            PostReviewActionSnapshot(
                id="fix-1",
                kind="bug",
                severity="high",
                title="Fix validation",
                status="pending",
            )
        ],
    )

    presentation = improve_result_command_presentation(result, snapshot)

    assert presentation.title == "Improve"
    assert presentation.body == "Queued supplemental work."
    assert presentation.severity == "info"
    assert presentation.table_columns == ("Item", "Value")
    assert ("Supplemental rounds", "1") in presentation.table_rows
    assert presentation.table_rows[-1][0] == "fix-1"
    assert "Fix validation" in presentation.table_rows[-1][1]
    assert presentation.action_hint == (
        "Use `/improve high`, `/improve all`, `/improve AI-001`, or `/improve done`."
    )


def test_improve_command_effect_skips_empty_message() -> None:
    effect = improve_command_effect(None, WorkflowNexusSnapshot(session_id="wf-empty"))

    assert effect.presentation is None


def test_improve_command_effect_builds_info_presentation() -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-improve",
        supplemental_round=2,
    )

    effect = improve_command_effect("Queued supplemental work.", snapshot)

    assert effect.presentation is not None
    assert effect.presentation.title == "Improve"
    assert effect.presentation.body == "Queued supplemental work."
    assert effect.presentation.severity == "info"
    assert ("Supplemental rounds", "2") in effect.presentation.table_rows


def test_improve_command_effect_builds_warning_presentation() -> None:
    effect = improve_command_effect(
        "Target workspace is required.",
        WorkflowNexusSnapshot(session_id="wf-warning"),
    )

    assert effect.presentation is not None
    assert effect.presentation.severity == "warning"
