from trinity.textual_app.ask_commands import ask_command_action, ask_error_presentation


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


def test_ask_command_action_returns_start_action_on_start_route() -> None:
    action = ask_command_action(
        ["claude", "--model", "sonnet", "분석해라"],
        ["claude", "codex"],
        current_route="start",
        lang="ko",
    )

    assert action.kind == "start"
    assert action.prompt == "분석해라"
    assert action.target_agents == ("claude",)
    assert action.agent_model_overrides == {"claude": "sonnet"}
    assert action.presentation is None


def test_ask_command_action_returns_follow_up_action_off_start_route() -> None:
    action = ask_command_action(
        ["all", "continue", "work"],
        ["claude", "codex"],
        current_route="nexus",
    )

    assert action.kind == "follow_up"
    assert action.prompt == "continue work"
    assert action.target_agents == ("claude", "codex")
    assert action.agent_model_overrides == {}
    assert action.presentation is None


def test_ask_command_action_returns_error_presentation() -> None:
    action = ask_command_action(
        ["missing", "hello"],
        ["claude"],
        current_route="nexus",
    )

    assert action.kind == "error"
    assert action.presentation is not None
    assert action.presentation.severity == "warning"
    assert "Unknown or disabled agent" in action.presentation.body
