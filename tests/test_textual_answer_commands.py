from trinity.textual_app.answer_commands import (
    answer_error_command_presentation,
    answer_message_command_presentation,
    answer_result_command_presentation,
    answer_result_presentation,
    run_answer_command,
)


class FakeAnswerController:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...], bool]] = []

    def answer_question(
        self,
        question_id: str,
        answer: str,
        *,
        replace: bool = False,
    ) -> str:
        self.calls.append(("answer_question", (question_id, answer), replace))
        return "free-form-outcome"

    def answer_question_option(
        self,
        option_index: str,
        *,
        question_selector: str = "next",
        replace: bool = False,
    ) -> str:
        self.calls.append(
            ("answer_question_option", (question_selector, option_index), replace)
        )
        return "option-outcome"


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


def test_answer_message_command_presentation_combines_message_and_payload() -> None:
    assert answer_message_command_presentation(None) is None

    presentation = answer_message_command_presentation("No pending question found.")

    assert presentation is not None
    assert presentation.title == "Answer"
    assert presentation.body == "No pending question found."
    assert presentation.severity == "warning"
    assert presentation.empty is True


def test_run_answer_command_returns_parse_error_without_controller_call() -> None:
    controller = FakeAnswerController()

    result = run_answer_command([], controller, lang="ko")

    assert result.outcome is None
    assert result.presentation is not None
    assert result.presentation.title == "답변"
    assert result.presentation.severity == "warning"
    assert controller.calls == []


def test_run_answer_command_routes_numeric_option() -> None:
    controller = FakeAnswerController()

    result = run_answer_command(["--replace", "2"], controller)

    assert result.outcome == "option-outcome"
    assert result.presentation is None
    assert controller.calls == [("answer_question_option", ("next", "2"), True)]


def test_run_answer_command_routes_next_answer() -> None:
    controller = FakeAnswerController()

    result = run_answer_command(["yes"], controller)

    assert result.outcome == "free-form-outcome"
    assert result.presentation is None
    assert controller.calls == [("answer_question", ("next", "yes"), False)]


def test_run_answer_command_routes_explicit_question_answer() -> None:
    controller = FakeAnswerController()

    result = run_answer_command(["q-1", "좋습니다", "진행하세요"], controller)

    assert result.outcome == "free-form-outcome"
    assert result.presentation is None
    assert controller.calls == [
        ("answer_question", ("q-1", "좋습니다 진행하세요"), False)
    ]
