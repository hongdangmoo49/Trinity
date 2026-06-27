from types import SimpleNamespace

from trinity.config import Provider
from trinity.slash_commands import SESSION_ONLY_SETTING_NOTICE
from trinity.textual_app.agent_commands import (
    agent_current_presentation,
    agent_error_presentation,
    agent_update_presentation,
)


def _agents() -> dict[str, SimpleNamespace]:
    return {
        "claude": SimpleNamespace(enabled=True, provider=Provider.CLAUDE_CODE),
        "codex": SimpleNamespace(enabled=False, provider=Provider.CODEX),
    }


def test_agent_current_presentation_describes_current_settings() -> None:
    presentation = agent_current_presentation(_agents())

    assert presentation.title == "Agent"
    assert presentation.body.startswith("Current agent session settings.")
    assert SESSION_ONLY_SETTING_NOTICE in presentation.body
    assert presentation.action_hint == "Use `/agent <name> on|off` to change one agent."
    assert presentation.table_columns == ("Agent", "Enabled", "Provider")
    assert presentation.table_rows == (
        ("claude", "yes", "claude-code"),
        ("codex", "no", "codex"),
    )


def test_agent_error_presentation_marks_warning_with_rows() -> None:
    presentation = agent_error_presentation("Usage: `/agent <name> on|off`", _agents())

    assert presentation.title == "Agent"
    assert presentation.body == "Usage: `/agent <name> on|off`"
    assert presentation.severity == "warning"
    assert presentation.table_rows == (
        ("claude", "yes", "claude-code"),
        ("codex", "no", "codex"),
    )


def test_agent_update_presentation_describes_updated_agent() -> None:
    agents = _agents()
    agents["codex"].enabled = True

    presentation = agent_update_presentation("codex", True, agents)

    assert presentation.title == "Agent"
    assert presentation.body.startswith("Agent `codex` enabled for this session only.")
    assert SESSION_ONLY_SETTING_NOTICE in presentation.body
    assert ("codex", "yes", "codex") in presentation.table_rows


def test_agent_presentation_uses_korean_labels() -> None:
    agents = _agents()
    agents["claude"].enabled = False

    current = agent_current_presentation(agents, lang="ko")
    updated = agent_update_presentation("claude", False, agents, lang="ko")
    error = agent_error_presentation("알 수 없는 에이전트: `missing`", agents, lang="ko")

    assert current.title == "에이전트"
    assert current.table_columns == ("에이전트", "활성화", "프로바이더")
    assert ("claude", "아니오", "claude-code") in current.table_rows
    assert updated.body.startswith("이 세션에서 에이전트 `claude`를 비활성화했습니다.")
    assert error.severity == "warning"
    assert error.title == "에이전트"
