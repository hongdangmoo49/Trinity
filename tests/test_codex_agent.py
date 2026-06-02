"""Tests for trinity.agents.codex_agent — CodexAgent."""

import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from trinity.agents.codex_agent import CodexAgent
from trinity.completion.base import CompletionResult
from trinity.models import AgentSpec, ContextUsage, MessageRole, Provider


@pytest.fixture
def codex_spec():
    return AgentSpec(
        name="codex",
        provider=Provider.CODEX,
        cli_command="codex",
        role_prompt="You are the Implementer.",
        context_budget=128_000,
    )


@pytest.fixture
def agent(codex_spec):
    return CodexAgent(codex_spec)


class TestCodexInit:
    def test_name(self, agent):
        assert agent.name == "codex"

    def test_context_budget(self, agent):
        assert agent.context_usage.total == 128_000

    def test_not_started(self, agent):
        assert not agent._started

    def test_session_dir(self, agent, tmp_path):
        agent.session_dir = tmp_path
        assert agent.session_dir == tmp_path


class TestCodexStart:
    @pytest.mark.asyncio
    async def test_start_print_mode(self, agent):
        await agent.start()
        assert agent._started

    @pytest.mark.asyncio
    async def test_start_with_initial_prompt(self, agent):
        await agent.start(initial_prompt="Welcome.")
        assert agent._initial_prompt == "Welcome."


class TestCodexSendAndWait:
    @pytest.mark.asyncio
    async def test_raises_if_not_started(self, agent):
        with pytest.raises(RuntimeError, match="not started"):
            await agent.send_and_wait("test")

    @pytest.mark.asyncio
    async def test_print_mode_subprocess(self, agent):
        await agent.start()

        mock_output = {
            "result": "I'll implement the auth module.",
            "usage": {"total_tokens": 5000},
        }

        with patch.object(agent, "_run_subprocess", return_value=mock_output):
            msg = await agent.send_and_wait("Implement auth.")

        assert msg.source == "codex"
        assert msg.role == MessageRole.OPINION
        assert "auth" in msg.content

    @pytest.mark.asyncio
    async def test_timeout(self, agent):
        import subprocess
        await agent.start()

        with patch.object(
            agent, "_run_subprocess",
            side_effect=subprocess.TimeoutExpired("cmd", 120)
        ):
            msg = await agent.send_and_wait("test", timeout=120)

        assert "Timeout" in msg.content

    @pytest.mark.asyncio
    async def test_error_exit_code(self, agent):
        await agent.start()

        with patch.object(agent, "_run_subprocess", return_value={
            "result": "[Error: exit code 1]",
            "usage": {},
        }):
            msg = await agent.send_and_wait("test")

        assert "Error" in msg.content

    @pytest.mark.asyncio
    async def test_interactive_mode_sends_prompt_before_waiting(self, codex_spec):
        pane = MagicMock()
        pane.is_alive.return_value = True
        detector = AsyncMock()
        detector.wait_for_completion.return_value = CompletionResult(
            completed=True,
            output="Codex response",
            detector_name="mock",
        )
        agent = CodexAgent(codex_spec, pane=pane, detector=detector)

        await agent.start(initial_prompt="Welcome.")
        msg = await agent.send_and_wait("Implement auth.")

        sent_prompt = pane.send_text_heredoc.call_args.args[0]
        assert "[System Role]" in sent_prompt
        assert "Welcome." in sent_prompt
        assert "Implement auth." in sent_prompt
        detector.wait_for_completion.assert_awaited_once_with(pane, timeout=120.0)
        assert msg.content == "Codex response"


class TestCodexBuildPrompt:
    def test_with_role(self, agent):
        prompt = agent._build_prompt("Implement auth.")
        assert "[System Role]" in prompt
        assert "Implementer" in prompt
        assert "Implement auth" in prompt


class TestCodexParseResponse:
    def test_normal(self, agent):
        data = {"result": "Code here.", "usage": {"total_tokens": 3000}}
        text, usage = agent._parse_response(data)
        assert text == "Code here."
        assert usage["used"] == 3000

    def test_missing_usage(self, agent):
        data = {"result": "Hello"}
        text, usage = agent._parse_response(data)
        assert usage["used"] == 0


class TestCodexSessionUsage:
    def test_parse_session_usage(self, agent, tmp_path):
        agent.session_dir = tmp_path
        (tmp_path / "session.json").write_text(
            json.dumps({"usage": {"total_tokens": 10000}}),
            encoding="utf-8",
        )
        result = agent._parse_session_usage()
        assert result is not None
        assert result.used == 10000

    def test_no_session_files(self, agent, tmp_path):
        agent.session_dir = tmp_path
        result = agent._parse_session_usage()
        assert result is None

    def test_no_session_dir(self, agent):
        agent.session_dir = None
        result = agent._parse_session_usage()
        assert result is None


class TestCodexIsAlive:
    @pytest.mark.asyncio
    async def test_alive_after_start(self, agent):
        await agent.start()
        assert await agent.is_alive() is True

    @pytest.mark.asyncio
    async def test_not_alive_after_shutdown(self, agent):
        await agent.start()
        await agent.graceful_shutdown()
        assert await agent.is_alive() is False


class TestCodexGetContextUsage:
    @pytest.mark.asyncio
    async def test_returns_usage(self, agent):
        usage = await agent.get_context_usage()
        assert isinstance(usage, ContextUsage)
        assert usage.total == 128_000
