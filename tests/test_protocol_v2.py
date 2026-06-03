"""Tests for Phase 2 protocol enhancements — pane title visualization."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from trinity.agents.base import AgentWrapper
from trinity.context.shared import SharedContextEngine
from trinity.deliberation.protocol import DeliberationProtocol
from trinity.models import (
    AgentSpec,
    ContextUsage,
    DeliberationMessage,
    MessageRole,
    Provider,
)


def _make_mock_agent(name: str) -> MagicMock:
    agent = MagicMock(spec=AgentWrapper)
    agent.name = name
    agent.spec = AgentSpec(
        name=name,
        provider=Provider.CLAUDE_CODE,
        cli_command="claude",
        role_prompt=f"You are {name}.",
    )
    agent.context_usage = ContextUsage(used=100, total=200_000)
    return agent


def _make_opinion(name: str, round_num: int, content: str) -> DeliberationMessage:
    return DeliberationMessage(
        source=name,
        target="all",
        round_num=round_num,
        role=MessageRole.OPINION,
        content=content,
    )


class TestUpdatePaneTitles:
    """Test _update_pane_titles with and without tmux_manager."""

    @pytest.mark.asyncio
    async def test_no_tmux_manager_does_nothing(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {"claude": _make_mock_agent("claude")}
        protocol = DeliberationProtocol(
            agents=agents, shared=engine, tmux_manager=None,
        )
        # Should not raise or call anything
        await protocol._update_pane_titles("Round 1/5")

    @pytest.mark.asyncio
    async def test_with_tmux_manager_updates_titles(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {"claude": _make_mock_agent("claude")}

        mock_tmux = MagicMock()
        mock_pane = MagicMock()
        mock_pane.pane_id = "%1"
        mock_tmux.get_pane = MagicMock(return_value=mock_pane)

        protocol = DeliberationProtocol(
            agents=agents, shared=engine, tmux_manager=mock_tmux,
        )

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_proc

            await protocol._update_pane_titles("Round 3/5")
            mock_exec.assert_called_once()
            call_args = mock_exec.call_args[0]
            assert "select-pane" in call_args
            assert "claude: Round 3/5" in call_args

    @pytest.mark.asyncio
    async def test_title_update_failure_does_not_crash(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {"claude": _make_mock_agent("claude")}

        mock_tmux = MagicMock()
        mock_pane = MagicMock()
        mock_pane.pane_id = "%1"
        mock_tmux.get_pane = MagicMock(return_value=mock_pane)

        protocol = DeliberationProtocol(
            agents=agents, shared=engine, tmux_manager=mock_tmux,
        )

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, side_effect=Exception("tmux error")):
            # Should not raise
            await protocol._update_pane_titles("test")

    @pytest.mark.asyncio
    async def test_title_for_missing_pane(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {"claude": _make_mock_agent("claude")}

        mock_tmux = MagicMock()
        mock_tmux.get_pane = MagicMock(return_value=None)  # No pane

        protocol = DeliberationProtocol(
            agents=agents, shared=engine, tmux_manager=mock_tmux,
        )

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            await protocol._update_pane_titles("Round 1/5")
            # Should not call subprocess since pane is None
            mock_exec.assert_not_called()


class TestProtocolWithTmuxManager:
    """Test that protocol passes tmux_manager to rounds correctly."""

    @pytest.mark.asyncio
    async def test_run_with_tmux_manager(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {"claude": _make_mock_agent("claude")}

        agents["claude"].send_and_wait = MagicMock(
            return_value=_make_opinion("claude", 1, "I agree with this."),
        )
        # Make it async
        async def async_send(prompt, timeout=120.0):
            return _make_opinion("claude", 1, "I agree with this.")
        agents["claude"].send_and_wait = async_send

        mock_tmux = MagicMock()
        mock_pane = MagicMock()
        mock_pane.pane_id = "%1"
        mock_tmux.get_pane = MagicMock(return_value=mock_pane)

        protocol = DeliberationProtocol(
            agents=agents,
            shared=engine,
            max_rounds=5,
            tmux_manager=mock_tmux,
        )

        with patch("subprocess.run"):
            result = await protocol.run("Test question")

            assert result.has_consensus
            assert result.rounds_completed == 1
