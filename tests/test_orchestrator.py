"""Tests for trinity.orchestrator — TrinityOrchestrator."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from trinity.config import TrinityConfig
from trinity.models import AgentSpec, DeliberationResult, ConsensusResult, Provider
from trinity.orchestrator import TrinityOrchestrator


class TestTrinityOrchestratorInit:
    """Test lazy initialization and component wiring."""

    def test_lazy_init_not_called_on_construction(self, tmp_path):
        config = TrinityConfig.default_config(project_dir=tmp_path)
        orch = TrinityOrchestrator(config)
        assert not orch.agents
        assert orch.shared is None
        assert orch.protocol is None

    def test_ensure_initializes_creates_components(self, tmp_path):
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=tmp_path / ".trinity",
            agents={
                "claude": AgentSpec(
                    name="claude",
                    provider=Provider.CLAUDE_CODE,
                    cli_command="claude",
                    role_prompt="You are a tester.",
                    enabled=True,
                ),
            },
        )
        orch = TrinityOrchestrator(config)
        orch._ensure_initialized()

        assert "claude" in orch.agents
        assert orch.shared is not None
        assert orch.protocol is not None

    def test_ensure_initializes_idempotent(self, tmp_path):
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=tmp_path / ".trinity",
            agents={
                "claude": AgentSpec(
                    name="claude",
                    provider=Provider.CLAUDE_CODE,
                    cli_command="claude",
                    role_prompt="Tester.",
                    enabled=True,
                ),
            },
        )
        orch = TrinityOrchestrator(config)
        orch._ensure_initialized()
        agents_before = dict(orch.agents)
        shared_before = orch.shared
        orch._ensure_initialized()
        # Should not recreate
        assert orch.agents == agents_before
        assert orch.shared is shared_before

    def test_ensure_initializes_creates_directories(self, tmp_path):
        state_dir = tmp_path / ".trinity"
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=state_dir,
            agents={
                "claude": AgentSpec(
                    name="claude",
                    provider=Provider.CLAUDE_CODE,
                    cli_command="claude",
                    enabled=True,
                ),
            },
        )
        orch = TrinityOrchestrator(config)
        orch._ensure_initialized()

        assert state_dir.exists()
        assert (state_dir / "agents").exists()
        assert (state_dir / "history").exists()
        assert (state_dir / "logs").exists()

    def test_no_active_agents_raises(self, tmp_path):
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=tmp_path / ".trinity",
            agents={
                "claude": AgentSpec(
                    name="claude",
                    provider=Provider.CLAUDE_CODE,
                    cli_command="claude",
                    enabled=False,
                ),
            },
        )
        orch = TrinityOrchestrator(config)
        with pytest.raises(ValueError, match="No active agents"):
            orch._ensure_initialized()


class TestAgentFactory:
    """Test _create_print_agent dispatches to correct agent class."""

    def test_claude_creates_print_mode(self, tmp_path):
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=tmp_path / ".trinity",
            agents={
                "claude": AgentSpec(
                    name="claude",
                    provider=Provider.CLAUDE_CODE,
                    cli_command="claude",
                    enabled=True,
                ),
            },
        )
        orch = TrinityOrchestrator(config)
        from trinity.agents.claude_agent import PrintModeClaudeAgent

        spec = config.agents["claude"]
        agent = orch._create_print_agent(spec)
        assert isinstance(agent, PrintModeClaudeAgent)

    def test_codex_creates_codex_agent(self, tmp_path):
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=tmp_path / ".trinity",
            agents={
                "codex": AgentSpec(
                    name="codex",
                    provider=Provider.CODEX,
                    cli_command="codex",
                    enabled=True,
                ),
            },
        )
        orch = TrinityOrchestrator(config)
        from trinity.agents.codex_agent import CodexAgent

        spec = config.agents["codex"]
        agent = orch._create_print_agent(spec)
        assert isinstance(agent, CodexAgent)

    def test_gemini_creates_gemini_agent(self, tmp_path):
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=tmp_path / ".trinity",
            agents={
                "gemini": AgentSpec(
                    name="gemini",
                    provider=Provider.GEMINI_CLI,
                    cli_command="gemini",
                    enabled=True,
                ),
            },
        )
        orch = TrinityOrchestrator(config)
        from trinity.agents.gemini_agent import GeminiAgent

        spec = config.agents["gemini"]
        agent = orch._create_print_agent(spec)
        assert isinstance(agent, GeminiAgent)

    def test_unknown_provider_raises(self, tmp_path):
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=tmp_path / ".trinity",
        )
        orch = TrinityOrchestrator(config)
        spec = AgentSpec(
            name="unknown",
            provider="claude-code",  # valid
            cli_command="test",
        )
        # Test with a monkeypatched invalid provider
        spec.provider = "invalid-provider"
        with pytest.raises(ValueError, match="Unknown provider"):
            orch._create_print_agent(spec)


class TestCompressionWiring:
    """Test that compression config flows from TrinityConfig to DeliberationProtocol."""

    def test_orchestrator_passes_compression_config(self, tmp_path):
        """Orchestrator should forward compression settings to DeliberationProtocol."""
        config = TrinityConfig.default_config(project_dir=tmp_path)
        config.prompt_compression_enabled = False
        config.prompt_compression_round_threshold = 3
        config.prompt_compression_max_summary_tokens = 300

        orchestrator = TrinityOrchestrator(config)
        orchestrator._ensure_initialized()

        assert orchestrator.protocol.compression_enabled is False
        assert orchestrator.protocol.compression_round_threshold == 3
        assert orchestrator.protocol.compressor is None  # disabled


class TestGetStatus:
    """Test get_status returns correct structure."""

    def test_status_structure(self, tmp_path):
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=tmp_path / ".trinity",
            agents={
                "claude": AgentSpec(
                    name="claude",
                    provider=Provider.CLAUDE_CODE,
                    cli_command="claude",
                    role_prompt="Tester.",
                    enabled=True,
                ),
            },
        )
        orch = TrinityOrchestrator(config)
        status = orch.get_status()

        assert "agents" in status
        assert "shared_context_path" in status
        assert "max_rounds" in status
        assert "claude" in status["agents"]
        assert status["agents"]["claude"]["provider"] == "claude-code"
        assert status["agents"]["claude"]["alive"] is True  # Print mode always alive
        assert status["max_rounds"] == config.max_deliberation_rounds


class TestAsk:
    """Test ask() orchestration flow with mocked agents."""

    @pytest.mark.asyncio
    async def test_ask_runs_protocol(self, tmp_path):
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=tmp_path / ".trinity",
            agents={
                "claude": AgentSpec(
                    name="claude",
                    provider=Provider.CLAUDE_CODE,
                    cli_command="claude",
                    role_prompt="Tester.",
                    enabled=True,
                ),
            },
        )
        orch = TrinityOrchestrator(config)

        # Mock the protocol's run method
        expected_result = DeliberationResult(
            user_prompt="test",
            rounds_completed=1,
            consensus=ConsensusResult(
                reached=True,
                agreement_count=1,
                total_agents=1,
                opinions={},
                summary="Test consensus.",
            ),
        )

        with patch.object(
            orch, "_ensure_initialized"
        ):
            orch.agents = {}
            from unittest.mock import MagicMock

            mock_agent = MagicMock()
            mock_agent.start = AsyncMock()
            mock_agent.spec = config.agents["claude"]
            mock_agent.context_usage = MagicMock()
            mock_agent.context_usage.used = 100
            orch.agents = {"claude": mock_agent}

            # Mock protocol creation
            from trinity.deliberation.protocol import DeliberationProtocol
            from unittest.mock import MagicMock as MM

            mock_protocol = MM(spec=DeliberationProtocol)
            mock_protocol.run = AsyncMock(return_value=expected_result)
            orch.protocol = mock_protocol
            orch.shared = MagicMock()

            result = await orch.ask("test prompt")

            assert result is expected_result
            assert result.user_prompt == "test"
            assert result.has_consensus
            mock_agent.start.assert_called_once()
            mock_protocol.run.assert_called_once_with("test prompt")
