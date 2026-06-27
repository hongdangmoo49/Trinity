from trinity.textual_app.answer_commands import (
    answer_error_command_presentation,
    answer_result_command_presentation,
    answer_result_presentation,
)


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


def test_answer_error_command_presentation_builds_warning_result() -> None:
    presentation = answer_error_command_presentation(
        "Answer text is required.",
        "Use `/answer q-1 yes`.",
    )

    assert presentation.title == "Answer"
    assert presentation.body == "Answer text is required."
    assert presentation.severity == "warning"
    assert presentation.empty is True
    assert presentation.action_hint == "Use `/answer q-1 yes`."


def test_answer_result_command_presentation_builds_local_result() -> None:
    result = answer_result_presentation("Answered question q-1.")
    assert result is not None

    presentation = answer_result_command_presentation(result)

    assert presentation.title == "Answer"
    assert presentation.body == "Answered question q-1."
    assert presentation.severity == "info"
    assert presentation.empty is False
    assert presentation.action_hint == ""


def test_answer_result_command_presentation_supports_korean_title() -> None:
    result = answer_result_presentation("질문 q-1에 답변했습니다.")
    assert result is not None

    presentation = answer_result_command_presentation(result, lang="ko")

    assert presentation.title == "답변"
    assert presentation.body == "질문 q-1에 답변했습니다."
