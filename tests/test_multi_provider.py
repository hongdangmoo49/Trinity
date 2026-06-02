"""Tests for multi-provider integration — AgentFactory + Orchestrator."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from trinity.agents.claude_agent import PrintModeClaudeAgent
from trinity.agents.codex_agent import CodexAgent
from trinity.agents.factory import AgentFactory
from trinity.agents.gemini_agent import GeminiAgent
from trinity.config import TrinityConfig
from trinity.models import AgentSpec, Provider
from trinity.orchestrator import TrinityOrchestrator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def multi_provider_config(tmp_path):
    """3-provider config for integration testing."""
    config = TrinityConfig(
        session_name="test-trinity",
        state_dir=tmp_path / "state",
        agents={
            "claude-agent": AgentSpec(
                name="claude-agent",
                provider=Provider.CLAUDE_CODE,
                cli_command="claude",
                role_prompt="You are a code reviewer.",
                enabled=True,
            ),
            "codex-agent": AgentSpec(
                name="codex-agent",
                provider=Provider.CODEX,
                cli_command="codex",
                role_prompt="You are an implementer.",
                enabled=True,
            ),
            "gemini-agent": AgentSpec(
                name="gemini-agent",
                provider=Provider.GEMINI_CLI,
                cli_command="gemini",
                role_prompt="You are a tester.",
                enabled=True,
            ),
        },
    )
    return config


@pytest.fixture
def orchestrator(multi_provider_config):
    return TrinityOrchestrator(config=multi_provider_config, interactive=False)


# ===========================================================================
# Multi-provider agent creation
# ===========================================================================

class TestMultiProviderCreation:
    """Verify each provider creates the correct agent type."""

    def test_three_providers_created(self, orchestrator):
        orchestrator._ensure_initialized()
        assert len(orchestrator.agents) == 3

    def test_claude_agent_type(self, orchestrator):
        orchestrator._ensure_initialized()
        agent = orchestrator.agents["claude-agent"]
        assert isinstance(agent, PrintModeClaudeAgent)

    def test_codex_agent_type(self, orchestrator):
        orchestrator._ensure_initialized()
        agent = orchestrator.agents["codex-agent"]
        assert isinstance(agent, CodexAgent)

    def test_gemini_agent_type(self, orchestrator):
        orchestrator._ensure_initialized()
        agent = orchestrator.agents["gemini-agent"]
        assert isinstance(agent, GeminiAgent)

    def test_each_agent_has_correct_provider(self, orchestrator):
        orchestrator._ensure_initialized()
        assert orchestrator.agents["claude-agent"].spec.provider == Provider.CLAUDE_CODE
        assert orchestrator.agents["codex-agent"].spec.provider == Provider.CODEX
        assert orchestrator.agents["gemini-agent"].spec.provider == Provider.GEMINI_CLI

    def test_each_agent_has_correct_role_prompt(self, orchestrator):
        orchestrator._ensure_initialized()
        assert orchestrator.agents["claude-agent"].spec.role_prompt == "You are a code reviewer."
        assert orchestrator.agents["codex-agent"].spec.role_prompt == "You are an implementer."
        assert orchestrator.agents["gemini-agent"].spec.role_prompt == "You are a tester."


# ===========================================================================
# Multi-provider component integration
# ===========================================================================

class TestMultiProviderComponents:
    """Verify orchestrator creates all components for multi-provider setup."""

    def test_health_checker_created(self, orchestrator):
        orchestrator._ensure_initialized()
        assert orchestrator.health_checker is not None
        assert len(orchestrator.health_checker.agents) == 3

    def test_context_monitor_created(self, orchestrator):
        orchestrator._ensure_initialized()
        assert orchestrator.context_monitor is not None

    def test_session_rotator_created(self, orchestrator):
        orchestrator._ensure_initialized()
        assert orchestrator.session_rotator is not None

    def test_protocol_created(self, orchestrator):
        orchestrator._ensure_initialized()
        assert orchestrator.protocol is not None

    def test_shared_context_created(self, orchestrator):
        orchestrator._ensure_initialized()
        assert orchestrator.shared is not None

    def test_tmux_manager_none_in_print_mode(self, orchestrator):
        orchestrator._ensure_initialized()
        assert orchestrator.tmux_manager is None


# ===========================================================================
# Multi-provider status
# ===========================================================================

class TestMultiProviderStatus:
    """Verify get_status() returns correct info for all providers."""

    def test_status_lists_all_agents(self, orchestrator):
        orchestrator._ensure_initialized()
        status = orchestrator.get_status()
        assert set(status["agents"].keys()) == {
            "claude-agent", "codex-agent", "gemini-agent",
        }

    def test_status_provider_values(self, orchestrator):
        orchestrator._ensure_initialized()
        status = orchestrator.get_status()
        assert status["agents"]["claude-agent"]["provider"] == "claude-code"
        assert status["agents"]["codex-agent"]["provider"] == "codex"
        assert status["agents"]["gemini-agent"]["provider"] == "gemini-cli"

    def test_status_interactive_false(self, orchestrator):
        orchestrator._ensure_initialized()
        status = orchestrator.get_status()
        assert status["interactive"] is False

    def test_status_no_tmux_session(self, orchestrator):
        orchestrator._ensure_initialized()
        status = orchestrator.get_status()
        assert status["tmux_session"] is None


# ===========================================================================
# Multi-provider context budgets
# ===========================================================================

class TestMultiProviderContextBudgets:
    """Verify each agent gets its provider-specific context budget."""

    def test_claude_budget(self, orchestrator):
        orchestrator._ensure_initialized()
        agent = orchestrator.agents["claude-agent"]
        # Default is 200k, but spec sets it from effective_context_budget
        assert agent.context_usage.total == agent.spec.effective_context_budget

    def test_codex_budget(self, orchestrator):
        orchestrator._ensure_initialized()
        agent = orchestrator.agents["codex-agent"]
        assert agent.context_usage.total == 128_000

    def test_gemini_budget(self, orchestrator):
        orchestrator._ensure_initialized()
        agent = orchestrator.agents["gemini-agent"]
        assert agent.context_usage.total == 1_000_000


# ===========================================================================
# Disabled agent handling
# ===========================================================================

class TestDisabledAgentHandling:
    """Verify disabled agents are excluded from multi-provider setup."""

    def test_disabled_agent_excluded(self, tmp_path):
        config = TrinityConfig(
            session_name="test",
            state_dir=tmp_path / "state",
            agents={
                "active": AgentSpec(
                    name="active",
                    provider=Provider.CLAUDE_CODE,
                    cli_command="claude",
                    enabled=True,
                ),
                "disabled": AgentSpec(
                    name="disabled",
                    provider=Provider.CODEX,
                    cli_command="codex",
                    enabled=False,
                ),
            },
        )
        orch = TrinityOrchestrator(config=config, interactive=False)
        orch._ensure_initialized()
        assert "active" in orch.agents
        assert "disabled" not in orch.agents

    def test_single_provider_works(self, tmp_path):
        config = TrinityConfig(
            session_name="test",
            state_dir=tmp_path / "state",
            agents={
                "solo": AgentSpec(
                    name="solo",
                    provider=Provider.GEMINI_CLI,
                    cli_command="gemini",
                    enabled=True,
                ),
            },
        )
        orch = TrinityOrchestrator(config=config, interactive=False)
        orch._ensure_initialized()
        assert len(orch.agents) == 1
        assert isinstance(orch.agents["solo"], GeminiAgent)


# ===========================================================================
# Factory standalone multi-provider tests
# ===========================================================================

class TestFactoryMultiProvider:
    """Direct AgentFactory multi-provider tests."""

    def test_create_all_print_modes(self):
        specs = [
            AgentSpec(name="c", provider=Provider.CLAUDE_CODE, cli_command="claude"),
            AgentSpec(name="x", provider=Provider.CODEX, cli_command="codex"),
            AgentSpec(name="g", provider=Provider.GEMINI_CLI, cli_command="gemini"),
        ]
        agents = [AgentFactory.create(s, mode="print") for s in specs]
        assert isinstance(agents[0], PrintModeClaudeAgent)
        assert isinstance(agents[1], CodexAgent)
        assert isinstance(agents[2], GeminiAgent)

    def test_each_detector_chain_differs(self, tmp_path):
        """각 provider의 detector chain 구조가 다름."""
        chains = {
            p: AgentFactory.create_detector_chain(tmp_path / "sig.json", p)
            for p in [Provider.CLAUDE_CODE, Provider.CODEX, Provider.GEMINI_CLI]
        }
        # Claude keeps hook + prompt, Codex prompt-only, Gemini marker + prompt.
        assert len(chains[Provider.CLAUDE_CODE].detectors) == 2
        assert len(chains[Provider.CODEX].detectors) == 1
        assert len(chains[Provider.GEMINI_CLI].detectors) == 2

        # Gemini chain starts with explicit marker detection, not idle.
        from trinity.completion.marker import MarkerDetector
        assert isinstance(chains[Provider.GEMINI_CLI].detectors[0], MarkerDetector)
