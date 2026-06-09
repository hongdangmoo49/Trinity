"""Tests for trinity.orchestrator — TrinityOrchestrator."""

import pytest
from unittest.mock import AsyncMock, patch

from trinity.config import TrinityConfig
from trinity.models import AgentSpec, DeliberationResult, ConsensusResult, Provider
from trinity.orchestrator import TrinityOrchestrator
from trinity.deliberation.synthesis import (
    FallbackSynthesisAgent,
    HeuristicSynthesisAgent,
    ModelBackedSynthesisAgent,
)
from trinity.providers.readiness import ProviderState, ReadinessResult
from trinity.workflow import ExecutionResult, WorkPackage, WorkStatus


class TestTrinityOrchestratorInit:
    """Test lazy initialization and component wiring."""

    def test_lazy_init_not_called_on_construction(self, tmp_path):
        config = TrinityConfig.default_config(project_dir=tmp_path)
        orch = TrinityOrchestrator(config)
        assert not orch.agents
        assert orch.shared is None
        assert orch.protocol is None

    def test_default_transport_uses_one_shot_mode(self, tmp_path):
        config = TrinityConfig.default_config(project_dir=tmp_path)
        orch = TrinityOrchestrator(config)

        assert orch.transport_mode == "one-shot"
        assert orch.interactive is False

    def test_transport_mode_tmux_enables_interactive_mode(self, tmp_path):
        config = TrinityConfig.default_config(project_dir=tmp_path)
        config.transport_mode = "tmux"
        orch = TrinityOrchestrator(config)

        assert orch.transport_mode == "tmux"
        assert orch.interactive is True

    def test_explicit_interactive_argument_overrides_transport_mode(self, tmp_path):
        config = TrinityConfig.default_config(project_dir=tmp_path)
        config.transport_mode = "tmux"
        orch = TrinityOrchestrator(config, interactive=False)

        assert orch.transport_mode == "one-shot"
        assert orch.interactive is False

    def test_ensure_initializes_creates_components(self, tmp_path):
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=tmp_path / ".trinity",
            execution_timeout_seconds=1234.0,
            parallel_shared_write_paths=["docs/guide.md"],
            parallel_broad_write_paths=["docs"],
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
        assert orch.execution_protocol is not None
        assert orch.execution_protocol.timeout == 1234.0
        assert orch.execution_protocol.parallel_policy.shared_write_paths == {
            "docs/guide.md"
        }
        assert orch.execution_protocol.parallel_policy.broad_write_paths == {"docs"}

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

    def test_restored_provider_session_is_attached_to_agent(self, tmp_path):
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
        orch = TrinityOrchestrator(
            config,
            provider_sessions={
                "codex:key": {
                    "agent_name": "codex",
                    "provider_session_id": "thread-1",
                    "access": "read-only",
                    "last_observed_at": 1.0,
                }
            },
        )

        orch._ensure_initialized()

        assert orch.agents["codex"].provider_session_id == "thread-1"


class TestWorkspaceHomeIsolation:
    """Test first-stage workspace/home launch metadata wiring."""

    def test_user_home_state_mode_does_not_create_managed_home(self, tmp_path):
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
            },
        )
        orch = TrinityOrchestrator(config)
        orch._ensure_initialized()

        claude_home = state_dir / "agents" / "claude" / "provider-state"
        codex_home = state_dir / "agents" / "codex" / "provider-state"

        assert not claude_home.exists()
        assert not codex_home.exists()
        assert orch.managed_home is None
        assert set(orch.agent_launch_contexts) == {"claude", "codex"}
        assert orch.agent_launch_contexts["claude"].managed_home is None
        assert orch.agent_launch_contexts["claude"].env_overrides == {}
        assert orch.get_agent_env_overrides("claude") == {}
        assert orch.get_agent_cwd("claude") == tmp_path.resolve()
        assert orch.agents["claude"].launch_cwd == tmp_path.resolve()
        assert orch.agents["claude"].env_overrides == {}

    def test_isolated_provider_state_mode_creates_managed_home(self, tmp_path):
        state_dir = tmp_path / ".trinity"
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=state_dir,
            provider_state_mode="isolated",
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
                    provider=Provider.ANTIGRAVITY_CLI,
                    cli_command="agy",
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

    def test_isolated_env_overrides_exposed_as_copy(self, tmp_path):
        state_dir = tmp_path / ".trinity"
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=state_dir,
            provider_state_mode="isolated",
            agents={
                "antigravity": AgentSpec(
                    name="antigravity",
                    provider=Provider.ANTIGRAVITY_CLI,
                    cli_command="agy",
                    enabled=True,
                ),
            },
        )
        orch = TrinityOrchestrator(config)
        orch._ensure_initialized()

        env = orch.get_agent_env_overrides("antigravity")
        expected_home = state_dir / "agents" / "antigravity" / "provider-state"
        assert env["HOME"] == str(expected_home)
        assert env["XDG_CONFIG_HOME"] == str(expected_home / ".config")

        env["HOME"] = "changed"
        assert orch.agent_launch_contexts["antigravity"].env_overrides["HOME"] == str(
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

    def test_target_workspace_overrides_inplace_launch_cwd(self, tmp_path):
        control_repo = tmp_path / "Trinity"
        target_workspace = tmp_path / "route-bot"
        state_dir = control_repo / ".trinity"
        target_workspace.mkdir(parents=True)
        config = TrinityConfig(
            project_dir=control_repo,
            state_dir=state_dir,
            agents={
                "claude": AgentSpec(
                    name="claude",
                    provider=Provider.CLAUDE_CODE,
                    cli_command="claude",
                    workspace_mode="inplace",
                    enabled=True,
                ),
            },
        )

        orch = TrinityOrchestrator(config, target_workspace=target_workspace)
        orch._ensure_initialized()

        assert orch.get_agent_cwd("claude") == target_workspace.resolve()
        assert orch.agents["claude"].launch_cwd == target_workspace.resolve()
        assert config.effective_state_dir == state_dir

    def test_git_worktree_workspace_mode_uses_target_workspace_root(self, tmp_path):
        control_repo = tmp_path / "Trinity"
        target_workspace = tmp_path / "route-bot"
        state_dir = control_repo / ".trinity"
        worktree_path = target_workspace / ".trinity" / "workspace" / "builder"
        target_workspace.mkdir(parents=True)
        config = TrinityConfig(
            project_dir=control_repo,
            state_dir=state_dir,
            agents={
                "builder": AgentSpec(
                    name="builder",
                    provider=Provider.CODEX,
                    cli_command="codex",
                    workspace_mode="git-worktree",
                    enabled=True,
                ),
            },
        )

        with patch("trinity.orchestrator.WorkspaceIsolation") as MockWorkspace:
            workspace = MockWorkspace.return_value
            workspace.create.return_value = worktree_path

            orch = TrinityOrchestrator(config, target_workspace=target_workspace)
            orch._ensure_initialized()

        MockWorkspace.assert_called_once_with(
            project_root=target_workspace.resolve(),
            state_dir=target_workspace.resolve() / ".trinity" / "workspace",
        )
        workspace.create.assert_called_once_with("builder")
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

    def test_antigravity_creates_antigravity_agent(self, tmp_path):
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=tmp_path / ".trinity",
            agents={
                "antigravity": AgentSpec(
                    name="antigravity",
                    provider=Provider.ANTIGRAVITY_CLI,
                    cli_command="agy",
                    enabled=True,
                ),
            },
        )
        orch = TrinityOrchestrator(config)
        from trinity.agents.antigravity_agent import AntigravityPrintAgent

        spec = config.agents["antigravity"]
        agent = orch._create_print_agent(spec)
        assert isinstance(agent, AntigravityPrintAgent)

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

    @pytest.mark.asyncio
    async def test_execute_work_packages_delegates_to_execution_protocol(self, tmp_path):
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
        package = WorkPackage(
            id="WP-001",
            title="codex package",
            owner_agent="codex",
            objective="Implement.",
        )
        expected = [
            ExecutionResult(
                package_id="WP-001",
                agent_name="codex",
                status=WorkStatus.DONE,
                summary="Done.",
            )
        ]

        with patch.object(orch, "_ensure_initialized"):
            from unittest.mock import MagicMock

            mock_execution = MagicMock()
            mock_execution.run = AsyncMock(return_value=expected)
            orch.execution_protocol = mock_execution

            result = await orch.execute_work_packages([package])

        assert result == expected
        mock_execution.run.assert_called_once_with([package], decisions=[])


class TestSynthesisAgentWiring:
    def test_heuristic_synthesis_mode_skips_model_provider(self, tmp_path):
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=tmp_path / ".trinity",
            synthesis_mode="heuristic",
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

        assert isinstance(orch.protocol.synthesis_agent, HeuristicSynthesisAgent)
        assert orch.synthesis_status["source"] == "heuristic"
        assert orch.synthesis_status["fallback_used"] is False

    def test_auto_synthesis_mode_wraps_model_agent_with_fallback(self, tmp_path):
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=tmp_path / ".trinity",
            agents={
                "claude": AgentSpec(
                    name="claude",
                    provider=Provider.CLAUDE_CODE,
                    cli_command="claude",
                    model="sonnet",
                    enabled=True,
                ),
            },
        )
        orch = TrinityOrchestrator(config)
        orch._ensure_initialized()

        assert isinstance(orch.protocol.synthesis_agent, FallbackSynthesisAgent)
        assert isinstance(orch.protocol.synthesis_agent.primary, ModelBackedSynthesisAgent)
        assert orch.protocol.synthesis_agent.primary.agent_name == "claude"
        assert orch.protocol.synthesis_agent.primary.model == "opus"
        assert orch.synthesis_status["source"] == "model-backed"

    def test_auto_synthesis_prioritizes_codex_over_agent_order(self, tmp_path):
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=tmp_path / ".trinity",
            agents={
                "antigravity": AgentSpec(
                    name="antigravity",
                    provider=Provider.ANTIGRAVITY_CLI,
                    cli_command="agy",
                    enabled=True,
                ),
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
        orch._ensure_initialized()

        primary = orch.protocol.synthesis_agent.primary
        assert isinstance(primary, ModelBackedSynthesisAgent)
        assert primary.agent_name == "codex"
        assert primary.provider == Provider.CODEX
        assert primary.model == "default"

    def test_auto_synthesis_uses_claude_when_codex_is_not_active(self, tmp_path):
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=tmp_path / ".trinity",
            agents={
                "antigravity": AgentSpec(
                    name="antigravity",
                    provider=Provider.ANTIGRAVITY_CLI,
                    cli_command="agy",
                    enabled=True,
                ),
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

        primary = orch.protocol.synthesis_agent.primary
        assert isinstance(primary, ModelBackedSynthesisAgent)
        assert primary.agent_name == "claude"
        assert primary.provider == Provider.CLAUDE_CODE
        assert primary.model == "opus"

    def test_fast_synthesis_model_uses_codex_agent_default_model(self, tmp_path):
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=tmp_path / ".trinity",
            synthesis_model="fast",
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
        orch._ensure_initialized()

        primary = orch.protocol.synthesis_agent.primary
        assert isinstance(primary, ModelBackedSynthesisAgent)
        assert primary.agent_name == "codex"
        assert primary.model == "default"
        assert primary.requested_model == "fast"

    def test_agent_default_synthesis_model_uses_selected_agent_model(self, tmp_path):
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=tmp_path / ".trinity",
            synthesis_agent="codex",
            synthesis_model="agent-default",
            agents={
                "codex": AgentSpec(
                    name="codex",
                    provider=Provider.CODEX,
                    cli_command="codex",
                    model="gpt-5",
                    enabled=True,
                ),
            },
        )
        orch = TrinityOrchestrator(config)
        orch._ensure_initialized()

        primary = orch.protocol.synthesis_agent.primary
        assert isinstance(primary, ModelBackedSynthesisAgent)
        assert primary.agent_name == "codex"
        assert primary.model == "gpt-5"
        assert primary.requested_model == "agent-default"

    def test_auto_synthesis_uses_antigravity_when_it_is_only_active(self, tmp_path):
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=tmp_path / ".trinity",
            agents={
                "antigravity": AgentSpec(
                    name="antigravity",
                    provider=Provider.ANTIGRAVITY_CLI,
                    cli_command="agy",
                    enabled=True,
                ),
            },
        )
        orch = TrinityOrchestrator(config)
        orch._ensure_initialized()

        primary = orch.protocol.synthesis_agent.primary
        assert isinstance(primary, ModelBackedSynthesisAgent)
        assert primary.agent_name == "antigravity"
        assert primary.provider == Provider.ANTIGRAVITY_CLI
        assert primary.model == "default"

    def test_synthesis_agent_override_selects_enabled_provider(self, tmp_path):
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=tmp_path / ".trinity",
            synthesis_agent="codex",
            synthesis_model="gpt-5.4-mini",
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
        orch._ensure_initialized()

        primary = orch.protocol.synthesis_agent.primary
        assert isinstance(primary, ModelBackedSynthesisAgent)
        assert primary.agent_name == "codex"
        assert primary.provider == Provider.CODEX
        assert primary.model == "gpt-5.4-mini"
        assert orch.synthesis_status["provider_agent"] == "codex"
