"""Tests for InteractiveClaudeAgent — tmux interactive mode."""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from trinity.agents.claude_agent import InteractiveClaudeAgent
from trinity.completion.base import CompletionDetector, CompletionResult, FallbackChainDetector
from trinity.completion.hook import HookDetector
from trinity.completion.idle import IdleDetector
from trinity.completion.prompt import PromptReturnDetector
from trinity.models import AgentSpec, ContextUsage, MessageRole, Provider
from trinity.tmux.pane import TmuxPane


@pytest.fixture
def mock_pane():
    pane = MagicMock(spec=TmuxPane)
    pane.pane_id = "%0"
    pane.session_name = "test"
    pane.is_alive = MagicMock(return_value=True)
    pane.capture = MagicMock(return_value=[])
    pane.send_text = MagicMock()
    pane.send_text_heredoc = MagicMock()
    return pane


@pytest.fixture
def signal_path(tmp_path):
    return tmp_path / "signal.json"


@pytest.fixture
def mock_detector():
    det = MagicMock(spec=CompletionDetector)
    det.name = "MockDetector"
    det.wait_for_completion = AsyncMock(return_value=CompletionResult(
        completed=True,
        output="AI response text\n> ",
        detector_name="MockDetector",
        elapsed_seconds=1.0,
    ))
    return det


@pytest.fixture
def agent_spec():
    return AgentSpec(
        name="claude",
        provider=Provider.CLAUDE_CODE,
        cli_command="claude",
        role_prompt="You are the Architect.",
        extra_args=["--dangerously-skip-permissions"],
    )


@pytest.fixture
def agent(agent_spec, mock_pane, mock_detector, signal_path):
    return InteractiveClaudeAgent(
        spec=agent_spec,
        pane=mock_pane,
        detector=mock_detector,
        signal_path=signal_path,
    )


class TestInteractiveInit:
    def test_name(self, agent):
        assert agent.name == "claude"

    def test_not_started(self, agent):
        assert not agent._started

    def test_pane_setter(self, agent_spec, mock_detector, signal_path):
        a = InteractiveClaudeAgent(spec=agent_spec, detector=mock_detector, signal_path=signal_path)
        assert a.pane is None
        a.pane = MagicMock()
        assert a.pane is not None

    def test_detector_setter(self, agent_spec, mock_pane, signal_path):
        a = InteractiveClaudeAgent(spec=agent_spec, pane=mock_pane, signal_path=signal_path)
        assert a.detector is None
        a.detector = MagicMock()
        assert a.detector is not None


class TestInteractiveStart:
    @pytest.mark.asyncio
    async def test_raises_without_pane(self, agent_spec, mock_detector, signal_path):
        a = InteractiveClaudeAgent(spec=agent_spec, detector=mock_detector, signal_path=signal_path)
        with pytest.raises(RuntimeError, match="No tmux pane"):
            await a.start()

    @pytest.mark.asyncio
    async def test_raises_without_detector(self, agent_spec, mock_pane, signal_path):
        a = InteractiveClaudeAgent(spec=agent_spec, pane=mock_pane, signal_path=signal_path)
        with pytest.raises(RuntimeError, match="No completion detector"):
            await a.start()

    @pytest.mark.asyncio
    async def test_launches_claude_in_pane(self, agent, mock_pane):
        # Mock: prompt appears quickly
        mock_pane.capture = MagicMock(return_value=["> "])

        await agent.start()
        assert agent._started
        mock_pane.send_text.assert_called()
        # Should have launched claude CLI
        assert any("claude" in str(c) for c in mock_pane.send_text.call_args_list)

    @pytest.mark.asyncio
    async def test_injects_role_prompt(self, agent, mock_pane, mock_detector):
        mock_pane.capture = MagicMock(return_value=["> "])

        await agent.start(initial_prompt="You are the reviewer.")
        # Role prompt should be sent via the detector flow
        assert agent._started


class TestInteractiveSendAndWait:
    @pytest.mark.asyncio
    async def test_raises_if_not_started(self, agent):
        with pytest.raises(RuntimeError, match="not started"):
            await agent.send_and_wait("test")

    @pytest.mark.asyncio
    async def test_sends_via_heredoc(self, agent, mock_pane, mock_detector):
        agent._started = True
        mock_pane.capture = MagicMock(return_value=["response", "> "])

        msg = await agent.send_and_wait("What framework?")

        mock_pane.send_text_heredoc.assert_called_once()
        assert msg.source == "claude"
        assert msg.role == MessageRole.OPINION
        assert msg.metadata["prompt_num"] == 1

    @pytest.mark.asyncio
    async def test_increments_prompt_counter(self, agent, mock_pane, mock_detector):
        agent._started = True
        mock_pane.capture = MagicMock(return_value=["response", "> "])

        await agent.send_and_wait("prompt 1")
        await agent.send_and_wait("prompt 2")

        assert agent._prompt_counter == 2

    @pytest.mark.asyncio
    async def test_returns_deliberation_message(self, agent, mock_pane, mock_detector):
        agent._started = True
        mock_pane.capture = MagicMock(return_value=["AI response", "> "])

        msg = await agent.send_and_wait("test")

        assert msg.source == "claude"
        assert msg.target == "all"
        assert msg.role == MessageRole.OPINION
        assert msg.metadata["detector"] == "MockDetector"


class TestExtractResponse:
    def test_extracts_after_sent_text(self, agent):
        agent._sent_text = "What framework should we use?"
        raw = "What framework should we use?\nI recommend JWT.\n> "
        result = agent._extract_response(raw)
        assert "JWT" in result
        assert "What framework" not in result

    def test_handles_no_match(self, agent):
        agent._sent_text = "some prompt"
        raw = "response line 1\nresponse line 2"
        result = agent._extract_response(raw)
        assert "response" in result

    def test_strips_trailing_prompt(self, agent):
        agent._sent_text = "prompt"
        raw = "prompt\nresponse\n> \n"
        result = agent._extract_response(raw)
        assert result.endswith("response")

    def test_empty_sent_text(self, agent):
        agent._sent_text = ""
        raw = "response text here"
        result = agent._extract_response(raw)
        assert "response" in result


class TestParseUsageFromOutput:
    def test_extracts_token_count(self, agent):
        output = "Response text\nTokens: 1234/200000\n> "
        result = agent._parse_usage_from_output(output)
        assert result["used"] == 1234
        assert result["total"] == 200000

    def test_extracts_usage_only(self, agent):
        output = "Response text\nUsage: 500\n"
        result = agent._parse_usage_from_output(output)
        assert result["used"] == 500

    def test_no_usage_returns_zero(self, agent):
        output = "Just a response with no usage info"
        result = agent._parse_usage_from_output(output)
        assert result["used"] == 0


class TestInteractiveIsAlive:
    @pytest.mark.asyncio
    async def test_alive_when_started(self, agent, mock_pane):
        agent._started = True
        assert await agent.is_alive() is True

    @pytest.mark.asyncio
    async def test_not_alive_when_not_started(self, agent, mock_pane):
        agent._started = False
        assert await agent.is_alive() is False

    @pytest.mark.asyncio
    async def test_not_alive_without_pane(self, agent_spec, mock_detector, signal_path):
        a = InteractiveClaudeAgent(spec=agent_spec, detector=mock_detector, signal_path=signal_path)
        a._started = True
        assert await a.is_alive() is False


class TestInteractiveShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_sends_exit(self, agent, mock_pane):
        agent._started = True
        await agent.graceful_shutdown()
        mock_pane.send_text.assert_called_with("/exit")
        assert not agent._started

    @pytest.mark.asyncio
    async def test_shutdown_without_pane(self, agent_spec, mock_detector, signal_path):
        a = InteractiveClaudeAgent(spec=agent_spec, detector=mock_detector, signal_path=signal_path)
        a._started = True
        await a.graceful_shutdown()  # Should not crash
        assert not a._started


class TestGetContextUsage:
    @pytest.mark.asyncio
    async def test_returns_usage(self, agent):
        usage = await agent.get_context_usage()
        assert isinstance(usage, ContextUsage)
        assert usage.total == 200_000
