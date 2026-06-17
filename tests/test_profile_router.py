"""Tests for profile-based task routing."""

from trinity.models import AgentProfile, AgentSpec, Provider
from trinity.routing.profile_router import ClassifiedTask, ProfileRouter


def test_profile_router_prefers_stronger_profile_for_task_kind():
    router = ProfileRouter()
    agents = {
        "claude": AgentSpec(
            name="claude",
            provider=Provider.CLAUDE_CODE,
            cli_command="claude",
        ),
        "codex": AgentSpec(
            name="codex",
            provider=Provider.CODEX,
            cli_command="codex",
        ),
    }

    decision = router.select_agent(
        agents,
        ClassifiedTask(kind="implementation", turn_mode="execute"),
    )

    assert decision is not None
    assert decision.agent_name == "codex"
    assert decision.task_kind == "implementation"
    assert "implementation strength" in decision.reason


def test_profile_router_honors_custom_strength_override():
    router = ProfileRouter()
    agents = {
        "claude": AgentSpec(
            name="claude",
            provider=Provider.CLAUDE_CODE,
            cli_command="claude",
            profile=AgentProfile(
                mission="Implementation-heavy Claude",
                strengths={"implementation": 1.0},
                supported_turn_modes=["execute"],
                routing_priority=1,
            ),
        ),
        "codex": AgentSpec(
            name="codex",
            provider=Provider.CODEX,
            cli_command="codex",
            profile=AgentProfile(
                mission="Docs-only Codex",
                strengths={"implementation": 0.1},
                supported_turn_modes=["execute"],
                routing_priority=10,
            ),
        ),
    }

    decision = router.select_agent(
        agents,
        ClassifiedTask(kind="implementation", turn_mode="execute"),
    )

    assert decision is not None
    assert decision.agent_name == "claude"

