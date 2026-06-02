"""Tests for trinity.orchestrator — TrinityOrchestrator."""

import pytest
from unittest.mock import AsyncMock, patch

from trinity.config import TrinityConfig
from trinity.models import AgentSpec, DeliberationResult, ConsensusResult, Provider
from trinity.orchestrator import TrinityOrchestrator
from trinity.providers.readiness import ProviderState, ReadinessResult


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


class TestWorkspaceHomeIsolation:
    """Test first-stage workspace/home launch metadata wiring."""

    def test_managed_home_created_for_each_active_agent(self, tmp_path):
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
                "codex": AgentSpec(
                    name="codex",
                    provider=Provider.CODEX,
                    cli_command="codex",
                    enabled=True,
                ),
                "disabled": AgentSpec(
                    name="disabled",
                    provider=Provider.GEMINI_CLI,
                    cli_command="gemini",
                    enabled=False,
                ),
            },
        )
        orch = TrinityOrchestrator(config)
        orch._ensure_initialized()

        claude_home = state_dir / "agents" / "claude" / "provider-state"
        codex_home = state_dir / "agents" / "codex" / "provider-state"
        disabled_home = state_dir / "agents" / "disabled" / "provider-state"

        assert claude_home.exists()
        assert (claude_home / ".claude").exists()
        assert codex_home.exists()
        assert (codex_home / ".codex").exists()
        assert not disabled_home.exists()

        assert set(orch.agent_launch_contexts) == {"claude", "codex"}
        assert orch.get_agent_cwd("claude") == tmp_path.resolve()
        assert orch.agent_launch_contexts["claude"].managed_home == claude_home
        assert orch.agents["claude"].launch_cwd == tmp_path.resolve()
        assert orch.agents["claude"].env_overrides["HOME"] == str(claude_home)

    def test_env_overrides_exposed_as_copy(self, tmp_path):
        state_dir = tmp_path / ".trinity"
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=state_dir,
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
        orch._ensure_initialized()

        env = orch.get_agent_env_overrides("gemini")
        expected_home = state_dir / "agents" / "gemini" / "provider-state"
        assert env["HOME"] == str(expected_home)
        assert env["XDG_CONFIG_HOME"] == str(expected_home / ".config")

        env["HOME"] = "changed"
        assert orch.agent_launch_contexts["gemini"].env_overrides["HOME"] == str(
            expected_home
        )

    def test_git_worktree_workspace_mode_prepares_launch_cwd(self, tmp_path):
        state_dir = tmp_path / ".trinity"
        worktree_path = state_dir / "workspace" / "builder"
        worktree_path.mkdir(parents=True)
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=state_dir,
            agents={
                "builder": AgentSpec(
                    name="builder",
                    provider=Provider.CODEX,
                    cli_command="codex",
                    workspace_mode="git-worktree",
                    enabled=True,
                ),
                "reviewer": AgentSpec(
                    name="reviewer",
                    provider=Provider.CLAUDE_CODE,
                    cli_command="claude",
                    workspace_mode="inplace",
                    enabled=True,
                ),
            },
        )

        with patch("trinity.orchestrator.WorkspaceIsolation") as MockWorkspace:
            workspace = MockWorkspace.return_value
            workspace.create.return_value = worktree_path

            orch = TrinityOrchestrator(config)
            orch._ensure_initialized()

        MockWorkspace.assert_called_once_with(
            project_root=tmp_path,
            state_dir=state_dir / "workspace",
        )
        workspace.create.assert_called_once_with("builder")

        builder_context = orch.agent_launch_contexts["builder"]
        reviewer_context = orch.agent_launch_contexts["reviewer"]
        assert builder_context.cwd == worktree_path
        assert builder_context.workspace_path == worktree_path
        assert reviewer_context.cwd == tmp_path.resolve()
        assert reviewer_context.workspace_path is None
        assert orch.get_agent_cwd("builder") == worktree_path
        assert orch.agents["builder"].launch_cwd == worktree_path


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

    @pytest.mark.asyncio
    async def test_ask_skips_protocol_when_readiness_fails(self, tmp_path):
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

        with patch.object(orch, "_ensure_initialized"):
            from unittest.mock import MagicMock

            mock_agent = MagicMock()
            mock_agent.start = AsyncMock()
            mock_agent.spec = config.agents["claude"]
            mock_agent.context_usage.used = 0
            orch.agents = {"claude": mock_agent}

            mock_protocol = MagicMock()
            mock_protocol.run = AsyncMock()
            orch.protocol = mock_protocol

            mock_gate = MagicMock()
            mock_gate.check_all.return_value = {
                "claude": ReadinessResult(
                    agent_name="claude",
                    provider=Provider.CLAUDE_CODE,
                    ready=False,
                    state=ProviderState.AUTH_REQUIRED,
                    reason="claude-code requires authentication",
                    action_hint="Run `claude` in a terminal.",
                    excerpt="OAuth URL",
                )
            }
            orch.readiness_gate = mock_gate

            result = await orch.ask("test prompt")

            mock_agent.start.assert_called_once()
            mock_protocol.run.assert_not_called()
            assert result.rounds_completed == 0
            assert not result.has_consensus
            assert "Deliberation was not started" in result.consensus.summary
            assert "auth_required" in result.consensus.summary

    @pytest.mark.asyncio
    async def test_ask_degraded_mode_uses_ready_agents_only(self, tmp_path):
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=tmp_path / ".trinity",
            provider_readiness_mode="degraded",
            agents={
                "claude": AgentSpec(
                    name="claude",
                    provider=Provider.CLAUDE_CODE,
                    cli_command="claude",
                    enabled=True,
                ),
                "codex": AgentSpec(
                    name="codex",
                    provider=Provider.CODEX,
                    cli_command="codex",
                    enabled=True,
                ),
            },
        )
        orch = TrinityOrchestrator(config)
        expected_result = DeliberationResult(
            user_prompt="test",
            rounds_completed=1,
            consensus=ConsensusResult(
                reached=True,
                agreement_count=1,
                total_agents=1,
                opinions={"claude": "yes"},
                summary="ok",
            ),
        )

        with patch.object(orch, "_ensure_initialized"):
            from unittest.mock import MagicMock

            claude = MagicMock()
            claude.start = AsyncMock()
            claude.spec = config.agents["claude"]
            claude.context_usage.used = 10
            codex = MagicMock()
            codex.start = AsyncMock()
            codex.spec = config.agents["codex"]
            codex.context_usage.used = 0
            orch.agents = {"claude": claude, "codex": codex}

            mock_protocol = MagicMock()
            mock_protocol.run = AsyncMock(return_value=expected_result)
            orch.protocol = mock_protocol

            mock_gate = MagicMock()
            mock_gate.check_all.return_value = {
                "claude": ReadinessResult(
                    agent_name="claude",
                    provider=Provider.CLAUDE_CODE,
                    ready=True,
                    state=ProviderState.READY,
                    reason="ready",
                    action_hint="",
                ),
                "codex": ReadinessResult(
                    agent_name="codex",
                    provider=Provider.CODEX,
                    ready=False,
                    state=ProviderState.MODEL_LOADING,
                    reason="model loading",
                    action_hint="Wait.",
                ),
            }
            orch.readiness_gate = mock_gate

            result = await orch.ask("test prompt")

            assert result is expected_result
            mock_protocol.run.assert_called_once_with("test prompt")
            assert set(orch.agents) == {"claude"}
            assert set(mock_protocol.agents) == {"claude"}
