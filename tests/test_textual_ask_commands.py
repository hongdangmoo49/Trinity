from trinity.textual_app.ask_commands import ask_error_presentation


def test_ask_error_presentation_marks_warning_and_empty_state() -> None:
    presentation = ask_error_presentation(
        "Use: /ask <all|agent[,agent...]> [--model MODEL] <prompt>"
    )

    assert presentation.title == "Ask"
    assert presentation.body == (
        "Use: /ask <all|agent[,agent...]> [--model MODEL] <prompt>"
    )
    assert presentation.severity == "warning"
    assert presentation.empty is True
    assert presentation.action_hint == (
        "/ask <all|agent[,agent...]> [--model MODEL] <prompt>"
    )


def test_ask_error_presentation_uses_korean_labels() -> None:
    presentation = ask_error_presentation(
        "사용법: /ask <all|agent[,agent...]> [--model MODEL] <prompt>",
        lang="ko",
    )

    assert presentation.title == "질문"
    assert presentation.body == (
        "사용법: /ask <all|agent[,agent...]> [--model MODEL] <prompt>"
    )
    assert presentation.severity == "warning"
    assert presentation.empty is True
    assert presentation.action_hint == (
        "/ask <all|agent[,agent...]> [--model MODEL] <prompt>"
    )
