from __future__ import annotations

from trinity.textual_app.command_parsers import (
    parse_agent_args,
    parse_answer_args,
    parse_ask_args,
    parse_caveman_args,
    parse_rounds_args,
)


def test_parse_ask_args_targets_agent_and_model() -> None:
    result = parse_ask_args(
        ["codex", "--model", "gpt-5", "설계", "검토"],
        ["claude", "codex"],
        lang="ko",
    )

    assert result.target_agents == ("codex",)
    assert result.agent_model_overrides == {"codex": "gpt-5"}
    assert result.prompt == "설계 검토"
    assert result.error == ""


def test_parse_ask_args_all_uses_active_agents() -> None:
    result = parse_ask_args(["all", "status"], ["claude", "codex"])

    assert result.target_agents == ("claude", "codex")
    assert result.agent_model_overrides == {}
    assert result.prompt == "status"


def test_parse_ask_args_localized_errors() -> None:
    assert parse_ask_args([], ["claude"], lang="ko").error == (
        "사용법: /ask <all|agent[,agent...]> [--model MODEL] <prompt>"
    )
    assert parse_ask_args(["missing", "안녕"], ["claude"], lang="ko").error == (
        "알 수 없거나 비활성화된 에이전트: missing"
    )
    assert parse_ask_args(["all", "--model"], ["claude"], lang="ko").error == (
        "--model 뒤에 모델을 입력하세요."
    )
    assert parse_ask_args(["all"], ["claude"], lang="ko").error == (
        "프롬프트를 입력하세요."
    )
    assert parse_ask_args(["all", "안녕"], [], lang="ko").error == (
        "/ask에 사용할 활성 에이전트가 없습니다."
    )


def test_parse_rounds_args_returns_current_request_for_empty_args() -> None:
    result = parse_rounds_args([], lang="ko")

    assert result.rounds is None
    assert result.error == ""
    assert result.action_hint == ""


def test_parse_rounds_args_validates_number_and_range() -> None:
    assert parse_rounds_args(["7"], lang="ko").rounds == 7

    invalid = parse_rounds_args(["abc"], lang="ko")
    assert invalid.rounds is None
    assert invalid.error == "숫자가 올바르지 않습니다."
    assert invalid.action_hint == "`/rounds <1..20>`를 사용하세요."

    out_of_range = parse_rounds_args(["21"], lang="ko")
    assert out_of_range.rounds is None
    assert out_of_range.error == "라운드는 1에서 20 사이여야 합니다."
    assert out_of_range.action_hint == "`/rounds <1..20>`를 사용하세요."


def test_parse_agent_args_returns_current_request_for_empty_args() -> None:
    result = parse_agent_args([], ["claude"], lang="ko")

    assert result.agent_name == ""
    assert result.enabled is None
    assert result.error == ""


def test_parse_agent_args_validates_name_and_action() -> None:
    enabled = parse_agent_args(["claude", "on"], ["claude", "codex"], lang="ko")
    assert enabled.agent_name == "claude"
    assert enabled.enabled is True
    assert enabled.error == ""

    disabled = parse_agent_args(["codex", "off"], ["claude", "codex"], lang="ko")
    assert disabled.agent_name == "codex"
    assert disabled.enabled is False
    assert disabled.error == ""

    missing_action = parse_agent_args(["claude"], ["claude"], lang="ko")
    assert missing_action.error == "사용법: `/agent <name> on|off`"

    unknown = parse_agent_args(["missing", "on"], ["claude"], lang="ko")
    assert unknown.agent_name == "missing"
    assert unknown.error == "알 수 없는 에이전트: `missing`"

    invalid_action = parse_agent_args(["claude", "maybe"], ["claude"], lang="ko")
    assert invalid_action.agent_name == "claude"
    assert invalid_action.error == "사용법: `/agent <name> on|off`"


def test_parse_caveman_args_returns_current_request_for_empty_args() -> None:
    result = parse_caveman_args([], lang="ko")

    assert result.enabled is None
    assert result.intensity == ""
    assert result.error == ""
    assert result.action_hint == ""


def test_parse_caveman_args_validates_mode_and_intensity() -> None:
    assert parse_caveman_args(["on"], lang="ko").enabled is True
    assert parse_caveman_args(["enable"], lang="ko").enabled is True
    assert parse_caveman_args(["off"], lang="ko").enabled is False
    assert parse_caveman_args(["disable"], lang="ko").enabled is False

    lite = parse_caveman_args(["lite"], lang="ko")
    assert lite.enabled is True
    assert lite.intensity == "lite"

    invalid = parse_caveman_args(["strange"], lang="ko")
    assert invalid.enabled is None
    assert invalid.error == "사용법: /caveman [on|off|lite|full|ultra]"
    assert invalid.action_hint == "허용 모드: on, off, lite, full, ultra."


def test_parse_answer_args_validates_required_answer() -> None:
    empty = parse_answer_args([], lang="ko")
    assert empty.error == "사용법: /answer <question-id|index|next> <answer>"
    assert empty.action_hint == "먼저 `/questions`를 실행해 대기 중인 질문을 확인하세요."
    assert empty.replace is False

    replace_only = parse_answer_args(["--replace"], lang="ko")
    assert replace_only.error == "사용법: /answer <question-id|index|next> <answer>"
    assert replace_only.replace is True


def test_parse_answer_args_routes_option_next_and_explicit_answer() -> None:
    option = parse_answer_args(["--replace", "2"], lang="ko")
    assert option.option_index == "2"
    assert option.question_selector == ""
    assert option.answer == ""
    assert option.replace is True

    next_answer = parse_answer_args(["네"], lang="ko")
    assert next_answer.option_index == ""
    assert next_answer.question_selector == "next"
    assert next_answer.answer == "네"
    assert next_answer.replace is False

    explicit = parse_answer_args(["q-1", "좋습니다", "진행하세요"], lang="ko")
    assert explicit.question_selector == "q-1"
    assert explicit.answer == "좋습니다 진행하세요"
    assert explicit.replace is False
