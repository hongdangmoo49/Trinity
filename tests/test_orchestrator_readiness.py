"""Tests for orchestrator readiness runtime extraction."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from trinity.config import TrinityConfig
from trinity.models import AgentSpec, Provider
from trinity.orchestrator_readiness import OrchestratorReadinessRuntime
from trinity.providers.policy import InvocationAccess
from trinity.providers.readiness import ProviderState, ReadinessResult
from trinity.tui.events import TUIEventType


def _agent(name: str, provider: Provider):
    agent = MagicMock()
    agent.spec = AgentSpec(
        name=name,
        provider=provider,
        cli_command=provider.value,
        enabled=True,
    )
    return agent


def _readiness(
    name: str,
    provider: Provider,
    *,
    ready: bool,
    state: ProviderState,
) -> ReadinessResult:
    return ReadinessResult(
        agent_name=name,
        provider=provider,
        ready=ready,
        state=state,
        reason=state.value,
        action_hint="",
    )


def test_interactive_readiness_degraded_returns_ready_agents(tmp_path):
    config = TrinityConfig(
        project_dir=tmp_path,
        state_dir=tmp_path / ".trinity",
        provider_readiness_mode="degraded",
    )
    agents = {
        "claude": _agent("claude", Provider.CLAUDE_CODE),
        "codex": _agent("codex", Provider.CODEX),
    }
    gate = MagicMock()
    gate.check_all.return_value = {
        "claude": _readiness(
            "claude",
            Provider.CLAUDE_CODE,
            ready=True,
            state=ProviderState.READY,
        ),
        "codex": _readiness(
            "codex",
            Provider.CODEX,
            ready=False,
            state=ProviderState.CLI_NOT_FOUND,
        ),
    }
    events = []
    runtime = OrchestratorReadinessRuntime(
        config=config,
        interactive=True,
        agents=agents,
        readiness_gate=gate,
        one_shot_preflight=None,
        event_emit=events.append,
    )

    outcome = runtime.check_provider_readiness(prompt="test", start_time=0)

    assert outcome.failure_result is None
    assert set(outcome.ready_agents or {}) == {"claude"}
    assert outcome.readiness_results is not None
    assert outcome.readiness_results["codex"].state == ProviderState.CLI_NOT_FOUND
    assert [event.type for event in events] == [
        TUIEventType.PROVIDER_READINESS,
        TUIEventType.PROVIDER_READINESS,
    ]


def test_one_shot_preflight_raise_formats_dispatch_failure(tmp_path):
    config = TrinityConfig(
        project_dir=tmp_path,
        state_dir=tmp_path / ".trinity",
        provider_readiness_mode="strict",
    )
    preflight = MagicMock()
    preflight.check_all.return_value = {
        "codex": _readiness(
            "codex",
            Provider.CODEX,
            ready=False,
            state=ProviderState.PERMISSION_PLAN_INVALID,
        )
    }
    runtime = OrchestratorReadinessRuntime(
        config=config,
        interactive=False,
        agents={"codex": _agent("codex", Provider.CODEX)},
        readiness_gate=None,
        one_shot_preflight=preflight,
    )

    with pytest.raises(RuntimeError) as exc_info:
        runtime.ensure_one_shot_preflight_or_raise(
            access=InvocationAccess.WORKSPACE_WRITE,
        )

    message = str(exc_info.value)
    assert "Provider dispatch was not started" in message
    assert "permission_plan_invalid" in message
