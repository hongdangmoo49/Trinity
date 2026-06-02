"""Tests for trinity.agents.claude_agent — PrintModeClaudeAgent."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from trinity.agents.claude_agent import PrintModeClaudeAgent
from trinity.models import AgentSpec, ContextUsage, MessageRole, Provider


@pytest.fixture
def claude_spec():
    return AgentSpec(
        name="claude",
        provider=Provider.CLAUDE_CODE,
        cli_command="claude",
        role_prompt="You are the Architect.",
        extra_args=["--dangerously-skip-permissions"],
    )


@pytest.fixture
def agent(claude_spec):
    return PrintModeClaudeAgent(claude_spec)


class TestPrintModeClaudeAgentInit:
    def test_name(self, agent):
        assert agent.name == "claude"

    def test_not_started(self, agent):
        assert not agent._started

    def test_context_usage_initialized(self, agent):
        assert agent.context_usage.total == 200_000
        assert agent.context_usage.used == 0

    def test_repr(self, agent):
        assert "PrintModeClaudeAgent" in repr(agent)
        assert "claude" in repr(agent)


class TestStart:
    @pytest.mark.asyncio
    async def test_start_marks_started(self, agent):
        await agent.start()
        assert agent._started

    @pytest.mark.asyncio
    async def test_start_with_initial_prompt(self, agent):
        await agent.start(initial_prompt="Welcome to Trinity.")
        assert agent._initial_prompt == "Welcome to Trinity."

    @pytest.mark.asyncio
    async def test_start_without_initial_prompt(self, agent):
        await agent.start()
        assert agent._initial_prompt == ""


class TestSendAndWait:
    @pytest.mark.asyncio
    async def test_raises_if_not_started(self, agent):
        with pytest.raises(RuntimeError, match="not started"):
            await agent.send_and_wait("test")

    @pytest.mark.asyncio
    async def test_sends_correct_command(self, agent):
        await agent.start()

        mock_result = {
            "result": "I recommend JWT.",
            "usage": {"input_tokens": 100, "output_tokens": 50},
            "model": "claude-sonnet-4-6",
        }

        with patch.object(agent, "_run_subprocess", return_value=mock_result):
            msg = await agent.send_and_wait("What auth method?")

            assert msg.source == "claude"
            assert msg.target == "all"
            assert msg.role == MessageRole.OPINION
            assert msg.content == "I recommend JWT."
            assert msg.metadata["token_count"] == 150
            assert msg.metadata["model"] == "claude-sonnet-4-6"

    @pytest.mark.asyncio
    async def test_updates_context_usage(self, agent):
        await agent.start()

        mock_result = {
            "result": "Response",
            "usage": {"input_tokens": 200, "output_tokens": 100},
        }

        with patch.object(agent, "_run_subprocess", return_value=mock_result):
            await agent.send_and_wait("test")

            assert agent.context_usage.used == 300
            assert agent.context_usage.total == 200_000

    @pytest.mark.asyncio
    async def test_timeout_returns_error_message(self, agent):
        import subprocess

        await agent.start()

        with patch.object(
            agent, "_run_subprocess", side_effect=subprocess.TimeoutExpired("cmd", 120)
        ):
            msg = await agent.send_and_wait("test", timeout=120)

            assert "Timeout" in msg.content
            assert msg.metadata["error"] == "timeout"

    @pytest.mark.asyncio
    async def test_increments_message_count(self, agent):
        await agent.start()

        mock_result = {"result": "ok", "usage": {}}

        with patch.object(agent, "_run_subprocess", return_value=mock_result):
            await agent.send_and_wait("test1")
            await agent.send_and_wait("test2")

            assert agent._message_count == 2


class TestBuildPrompt:
    def test_with_role_and_initial(self, agent):
        agent._initial_prompt = "Welcome."
        prompt = agent._build_prompt("What should we do?")

        assert "[System Role]" in prompt
        assert "Architect" in prompt
        assert "[Context]" in prompt
        assert "Welcome" in prompt
        assert "What should we do?" in prompt

    def test_with_role_only(self, agent):
        agent._initial_prompt = ""
        prompt = agent._build_prompt("Test question")

        assert "[System Role]" in prompt
        assert "Test question" in prompt
        assert "[Context]" not in prompt

    def test_without_role(self):
        spec = AgentSpec(
            name="test",
            provider=Provider.CLAUDE_CODE,
            cli_command="claude",
            role_prompt="",
        )
        agent = PrintModeClaudeAgent(spec)
        agent._initial_prompt = ""

        prompt = agent._build_prompt("Just a question")
        assert prompt == "Just a question"


class TestRunSubprocess:
    def test_success_json(self, agent):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps({
            "result": "Hello",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        })

        with patch("subprocess.run", return_value=mock_proc):
            result = agent._run_subprocess(["claude", "-p", "test"], 120)

            assert result["result"] == "Hello"
            assert result["usage"]["input_tokens"] == 10

    def test_nonzero_exit_code(self, agent):
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = "Error: something went wrong"

        with patch("subprocess.run", return_value=mock_proc):
            result = agent._run_subprocess(["claude", "-p", "test"], 120)

            assert "Error" in result["result"]
            assert result["usage"] == {}

    def test_non_json_output(self, agent):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Plain text response, not JSON"

        with patch("subprocess.run", return_value=mock_proc):
            result = agent._run_subprocess(["claude", "-p", "test"], 120)

            assert result["result"] == "Plain text response, not JSON"

    def test_subprocess_uses_configured_launch_context(self, agent, tmp_path):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps({"result": "Hello", "usage": {}})
        agent.configure_launch(
            cwd=tmp_path,
            env_overrides={"HOME": str(tmp_path / "home")},
        )

        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            agent._run_subprocess(["claude", "-p", "test"], 120)

        kwargs = mock_run.call_args.kwargs
        assert kwargs["cwd"] == tmp_path
        assert kwargs["env"]["HOME"] == str(tmp_path / "home")


class TestParseResponse:
    def test_normal_response(self, agent):
        data = {
            "result": "Use JWT for auth.",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }
        text, usage = agent._parse_response(data)

        assert text == "Use JWT for auth."
        assert usage["used"] == 150
        assert usage["total"] == 200_000

    def test_missing_usage(self, agent):
        data = {"result": "Hello"}
        text, usage = agent._parse_response(data)

        assert text == "Hello"
        assert usage["used"] == 0

    def test_empty_usage(self, agent):
        data = {"result": "Hello", "usage": {}}
        text, usage = agent._parse_response(data)

        assert usage["used"] == 0


class TestGetContextUsage:
    @pytest.mark.asyncio
    async def test_returns_current_usage(self, agent):
        usage = await agent.get_context_usage()
        assert isinstance(usage, ContextUsage)
        assert usage.total == 200_000


class TestIsAlive:
    @pytest.mark.asyncio
    async def test_alive_after_start(self, agent):
        await agent.start()
        assert await agent.is_alive() is True

    @pytest.mark.asyncio
    async def test_not_alive_before_start(self, agent):
        assert await agent.is_alive() is False

    @pytest.mark.asyncio
    async def test_not_alive_after_shutdown(self, agent):
        await agent.start()
        await agent.graceful_shutdown()
        assert await agent.is_alive() is False


class TestGracefulShutdown:
    @pytest.mark.asyncio
    async def test_shutdown(self, agent):
        await agent.start()
        assert agent._started

        await agent.graceful_shutdown()
        assert not agent._started
