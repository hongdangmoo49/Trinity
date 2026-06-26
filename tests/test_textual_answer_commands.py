from trinity.textual_app.answer_commands import answer_result_presentation


def test_answer_result_presentation_skips_empty_message() -> None:
    assert answer_result_presentation(None) is None
    assert answer_result_presentation("") is None


def test_answer_result_presentation_marks_no_message_as_warning() -> None:
    presentation = answer_result_presentation("No pending question found.")

    assert presentation is not None
    assert presentation.message == "No pending question found."
    assert presentation.severity == "warning"
    assert presentation.empty is True


def test_answer_result_presentation_keeps_success_message_as_info() -> None:
    presentation = answer_result_presentation("Answered question q-1.")

    assert presentation is not None
    assert presentation.severity == "info"
    assert presentation.empty is False
