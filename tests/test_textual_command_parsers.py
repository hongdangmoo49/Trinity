from __future__ import annotations

from trinity.textual_app.command_parsers import parse_ask_args


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
