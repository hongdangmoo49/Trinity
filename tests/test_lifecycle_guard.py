"""Tests for workflow lifecycle guard hooks."""

from trinity.models import AgentSpec, ContextUsage, Provider
from trinity.providers.readiness import ProviderState, ReadinessResult
from trinity.workflow.lifecycle import (
    LifecycleActionKind,
    LifecycleGuard,
    LifecycleHook,
    LifecycleReason,
)
from trinity.workflow.models import WorkPackage


class FakePane:
    def __init__(self, alive: bool = True, lines: list[str] | None = None):
        self.alive = alive
        self.lines = lines or [">"]

    def is_alive(self) -> bool:
        return self.alive

    def capture(self, lines: int = -80) -> list[str]:
        return self.lines


class FakeAgent:
    def __init__(
        self,
        name: str,
        *,
        provider: Provider = Provider.CLAUDE_CODE,
        used: int = 0,
        total: int = 200_000,
        alive: bool = True,
        pane_lines: list[str] | None = None,
    ):
        self.name = name
        self.spec = AgentSpec(name=name, provider=provider, cli_command=provider.value)
        self._context_usage = ContextUsage(used=used, total=total)
        self.pane = FakePane(alive=alive, lines=pane_lines)

    @property
    def context_usage(self) -> ContextUsage:
        return self._context_usage


def _not_ready(agent_name: str = "codex") -> ReadinessResult:
    return ReadinessResult(
        agent_name=agent_name,
        provider=Provider.CODEX,
        ready=False,
        state=ProviderState.MODEL_LOADING,
        reason="codex is still loading a model",
        action_hint="Wait for Codex model initialization to finish, then retry.",
        excerpt="gpt-5.5 default",
    )


def test_before_agent_call_allows_continue_when_agent_is_healthy():
    guard = LifecycleGuard()
    agent = FakeAgent("claude", used=20_000, total=200_000)

    decision = guard.before_agent_call(agent)

    assert decision.hook == LifecycleHook.BEFORE_AGENT_CALL
    assert decision.can_continue is True
    assert decision.actions[0].kind == LifecycleActionKind.CONTINUE
    assert decision.actions[0].reason == LifecycleReason.OK


def test_before_agent_call_recommends_rotation_at_context_threshold():
    guard = LifecycleGuard(rotate_threshold=0.60)
    agent = FakeAgent("claude", used=120_000, total=200_000)

    decision = guard.before_agent_call(agent)

    assert decision.can_continue is False
    assert decision.needs_rotation is True
    assert decision.rotation_agents == ("claude",)
    assert decision.actions[0].kind == LifecycleActionKind.ROTATE_SESSION
    assert decision.actions[0].reason == LifecycleReason.CONTEXT_THRESHOLD
    assert decision.actions[0].details["ratio"] == 0.60


def test_before_agent_call_recommends_rotation_for_projected_ratio():
    guard = LifecycleGuard(rotate_threshold=0.60)
    agent = FakeAgent("claude", used=100_000, total=200_000)

    decision = guard.before_agent_call(agent, projected_tokens=25_000)

    assert decision.can_continue is False
    assert decision.needs_rotation is True
    assert decision.actions[0].reason == LifecycleReason.PROJECTED_RATIO
    assert decision.actions[0].details["projected_tokens"] == 25_000
    assert decision.actions[0].details["projected_ratio"] == 0.625


def test_before_agent_call_recommends_restart_when_process_is_dead():
    guard = LifecycleGuard()
    agent = FakeAgent("claude", alive=False)

    decision = guard.before_agent_call(agent)

    assert decision.can_continue is False
    assert decision.actions[0].kind == LifecycleActionKind.RESTART_PROCESS
    assert decision.actions[0].reason == LifecycleReason.PROCESS_NOT_ALIVE
    assert "Restart claude" in decision.recommendations[0]


def test_before_agent_call_recommends_wait_when_readiness_unavailable():
    guard = LifecycleGuard(check_readiness=False)
    agent = FakeAgent("codex", provider=Provider.CODEX)

    decision = guard.before_agent_call(agent, readiness=_not_ready())

    assert decision.can_continue is False
    assert decision.actions[0].kind == LifecycleActionKind.WAIT_FOR_READY
    assert decision.actions[0].reason == LifecycleReason.READINESS_UNAVAILABLE
    assert decision.actions[0].details["state"] == ProviderState.MODEL_LOADING.value
    assert "Codex model initialization" in decision.recommendations[0]


def test_after_agent_call_uses_supplied_token_usage():
    guard = LifecycleGuard(rotate_threshold=0.60)
    agent = FakeAgent(
        "antigravity",
        provider=Provider.ANTIGRAVITY_CLI,
        used=10,
        total=1_000,
    )

    decision = guard.after_agent_call(
        agent,
        token_usage=ContextUsage(used=650, total=1_000),
    )

    assert decision.hook == LifecycleHook.AFTER_AGENT_CALL
    assert decision.actions[0].reason == LifecycleReason.CONTEXT_THRESHOLD
    assert decision.actions[0].details["used"] == 650


def test_before_round_aggregates_agent_actions_and_projected_ratios():
    guard = LifecycleGuard(rotate_threshold=0.60, check_readiness=False)
    agents = {
        "claude": FakeAgent("claude", used=20_000, total=200_000),
        "codex": FakeAgent("codex", provider=Provider.CODEX, used=70_000, total=128_000),
    }

    decision = guard.before_round(
        agents,
        projected_tokens_by_agent={"claude": 110_000},
        readiness_by_agent={"codex": _not_ready()},
    )

    reasons = {action.agent_name: action.reason for action in decision.actions}
    assert decision.hook == LifecycleHook.BEFORE_ROUND
    assert reasons["claude"] == LifecycleReason.PROJECTED_RATIO
    assert reasons["codex"] == LifecycleReason.READINESS_UNAVAILABLE
    assert decision.metadata["checked_agents"] == ["claude", "codex"]


def test_after_round_checks_current_thresholds():
    guard = LifecycleGuard(rotate_threshold=0.60, check_readiness=False)
    agents = {
        "claude": FakeAgent("claude", used=121_000, total=200_000),
        "codex": FakeAgent("codex", provider=Provider.CODEX, used=10_000, total=128_000),
    }

    decision = guard.after_round(agents)

    assert decision.hook == LifecycleHook.AFTER_ROUND
    assert decision.rotation_agents == ("claude",)
    assert decision.actions[0].reason == LifecycleReason.CONTEXT_THRESHOLD


def test_before_work_package_checks_only_owner_agent():
    guard = LifecycleGuard(rotate_threshold=0.60, check_readiness=False)
    package = WorkPackage(
        id="WP-001",
        title="Implement API",
        owner_agent="codex",
        objective="Implement route API.",
    )
    agents = {
        "claude": FakeAgent("claude", used=180_000, total=200_000),
        "codex": FakeAgent("codex", provider=Provider.CODEX, used=10_000, total=128_000),
    }

    decision = guard.before_work_package(package, agents)

    assert decision.can_continue is True
    assert decision.actions[0].kind == LifecycleActionKind.CONTINUE
    assert decision.metadata["package_id"] == "WP-001"
    assert decision.metadata["checked_agents"] == ["codex"]


def test_before_work_package_reports_missing_owner():
    guard = LifecycleGuard(check_readiness=False)
    package = WorkPackage(
        id="WP-404",
        title="Missing owner",
        owner_agent="antigravity",
        objective="Run missing owner work.",
    )

    decision = guard.before_work_package(package, agents={})

    assert decision.can_continue is False
    assert decision.actions[0].kind == LifecycleActionKind.SKIP_AGENT
    assert decision.actions[0].reason == LifecycleReason.AGENT_UNAVAILABLE
    assert decision.metadata["owner_agent"] == "antigravity"


def test_after_work_package_returns_structured_serializable_decision():
    guard = LifecycleGuard(rotate_threshold=0.60, check_readiness=False)
    package = WorkPackage(
        id="WP-002",
        title="Check result",
        owner_agent="claude",
        objective="Review execution result.",
    )
    agent = FakeAgent("claude", used=150_000, total=200_000)

    decision = guard.after_work_package(package, {"claude": agent})
    data = decision.to_dict()

    assert decision.hook == LifecycleHook.AFTER_WORK_PACKAGE
    assert data["hook"] == "after_work_package"
    assert data["can_continue"] is False
    assert data["actions"][0]["kind"] == "rotate_session"
    assert data["actions"][0]["details"]["used"] == 150_000
