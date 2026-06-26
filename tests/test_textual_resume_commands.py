from trinity.textual_app.resume_commands import (
    resume_result_presentation,
    should_continue_resumed_workflow,
)


def test_resume_result_presentation_skips_empty_message() -> None:
    assert resume_result_presentation(None) is None
    assert resume_result_presentation("") is None


def test_resume_result_presentation_marks_no_message_as_failure() -> None:
    presentation = resume_result_presentation("No saved workflow found.")

    assert presentation is not None
    assert presentation.failed is True
    assert presentation.severity == "warning"
    assert presentation.empty is True
    assert presentation.start_modal is True
    assert should_continue_resumed_workflow(presentation) is False


def test_resume_result_presentation_keeps_info_message_continuable() -> None:
    presentation = resume_result_presentation("Resumed workflow wf-1.")

    assert presentation is not None
    assert presentation.failed is False
    assert presentation.severity == "info"
    assert presentation.empty is False
    assert presentation.start_modal is False
    assert should_continue_resumed_workflow(presentation) is True


def test_should_continue_resumed_workflow_without_message() -> None:
    assert should_continue_resumed_workflow(None) is True
