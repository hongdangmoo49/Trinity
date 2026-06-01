"""Tests for tmux integration — session + agent + protocol flow."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from trinity.agents.claude_agent import InteractiveClaudeAgent
from trinity.completion.base import CompletionResult
from trinity.config import TrinityConfig
from trinity.models import AgentSpec, Provider
from trinity.orchestrator import TrinityOrchestrator


class TestInteractiveModeInit:
    """Test that interactive mode creates tmux session and agents correctly."""

    def test_creates_tmux_manager_in_interactive_mode(self, tmp_path):
        config = TrinityConfig(
            project_dir=tmp_path,
            state_dir=tmp_path / ".trinity",
            agents={
                "claude": AgentSpec(
                    name="claude",
                    provider=Provider.CLAUDE_CODE,
                    cli_command="claude",
                    role_prompt="Architect.",
                    enabled=True,
                ),
            },
        )

        with patch("trinity.orchestrator.TmuxSessionManager") as MockTmux:
            mock_tmux_instance = MagicMock()
            mock_tmux_instance.get_pane = MagicMock(return_value=MagicMock(
                pane_id="%1", session_name="trinity",
            ))
            MockTmux.return_value = mock_tmux_instance

            orch = TrinityOrchestrator(config, interactive=True)
            orch._ensure_initialized()

            MockTmux.assert_called_once_with(session_name="trinity")
            mock_tmux_instance.create_session.assert_called_once()
            assert orch.tmux_manager is not None
            assert "claude" in orch.agents
            assert isinstance(orch.agents["claude"], InteractiveClaudeAgent)

    def test_print_mode_does_not_create_tmux(self, tmp_path):
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
        orch = TrinityOrchestrator(config, interactive=False)
        orch._ensure_initialized()

        assert orch.tmux_manager is None
        assert not isinstance(orch.agents["claude"], InteractiveClaudeAgent)

    def test_interactive_status_includes_tmux_info(self, tmp_path):
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

        with patch("trinity.orchestrator.TmuxSessionManager") as MockTmux:
            mock_tmux_instance = MagicMock()
            mock_tmux_instance.get_pane = MagicMock(return_value=MagicMock(
                pane_id="%1", session_name="trinity",
            ))
            MockTmux.return_value = mock_tmux_instance

            orch = TrinityOrchestrator(config, interactive=True)
            status = orch.get_status()

            assert status["interactive"] is True
            assert status["tmux_session"] == "trinity"

    def test_print_mode_status(self, tmp_path):
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
        orch = TrinityOrchestrator(config, interactive=False)
        status = orch.get_status()

        assert status["interactive"] is False
        assert status["tmux_session"] is None


class TestDetectorChain:
    """Test that the detector chain is constructed correctly."""

    def test_creates_fallback_chain(self, tmp_path):
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

        with patch("trinity.orchestrator.TmuxSessionManager") as MockTmux:
            mock_tmux_instance = MagicMock()
            mock_pane = MagicMock(pane_id="%1", session_name="trinity")
            mock_tmux_instance.get_pane = MagicMock(return_value=mock_pane)
            MockTmux.return_value = mock_tmux_instance

            orch = TrinityOrchestrator(config, interactive=True)
            orch._ensure_initialized()

            agent = orch.agents["claude"]
            from trinity.completion.base import FallbackChainDetector
            assert isinstance(agent.detector, FallbackChainDetector)
            assert len(agent.detector.detectors) == 3
            assert "Hook" in agent.detector.detectors[0].name
            assert "PromptReturn" in agent.detector.detectors[1].name
            assert "Idle" in agent.detector.detectors[2].name


class TestOrchestratorShutdown:
    """Test graceful shutdown of interactive mode."""

    @pytest.mark.asyncio
    async def test_shutdown_calls_agent_shutdown(self, tmp_path):
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

        with patch("trinity.orchestrator.TmuxSessionManager") as MockTmux:
            mock_tmux_instance = MagicMock()
            mock_pane = MagicMock(pane_id="%1", session_name="trinity")
            mock_tmux_instance.get_pane = MagicMock(return_value=mock_pane)
            MockTmux.return_value = mock_tmux_instance

            orch = TrinityOrchestrator(config, interactive=True)
            orch._ensure_initialized()

            # Mock agent shutdown
            orch.agents["claude"].graceful_shutdown = AsyncMock()

            await orch.shutdown()

            orch.agents["claude"].graceful_shutdown.assert_called_once()
            mock_tmux_instance.destroy.assert_called_once()
