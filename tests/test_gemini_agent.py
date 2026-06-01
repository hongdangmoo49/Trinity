"""Tests for trinity.agents.gemini_agent — GeminiAgent."""

import pytest
from unittest.mock import MagicMock, patch

from trinity.agents.gemini_agent import GeminiAgent, COMPLETION_MARKER
from trinity.models import AgentSpec, ContextUsage, MessageRole, Provider


@pytest.fixture
def gemini_spec():
    return AgentSpec(
        name="gemini",
        provider=Provider.GEMINI_CLI,
        cli_command="gemini",
        role_prompt="You are the Reviewer.",
        context_budget=1_000_000,
    )


@pytest.fixture
def agent(gemini_spec):
    return GeminiAgent(gemini_spec)


class TestGeminiInit:
    def test_name(self, agent):
        assert agent.name == "gemini"

    def test_context_budget(self, agent):
        assert agent.context_usage.total == 1_000_000

    def test_not_started(self, agent):
        assert not agent._started

    def test_hard_timeout_default(self, agent):
        assert agent._hard_timeout == 120.0


class TestGeminiStart:
    @pytest.mark.asyncio
    async def test_start_print_mode(self, agent):
        await agent.start()
        assert agent._started

    @pytest.mark.asyncio
    async def test_start_with_initial_prompt(self, agent):
        await agent.start(initial_prompt="Welcome.")
        assert agent._initial_prompt == "Welcome."


class TestGeminiSendAndWait:
    @pytest.mark.asyncio
    async def test_raises_if_not_started(self, agent):
        with pytest.raises(RuntimeError, match="not started"):
            await agent.send_and_wait("test")

    @pytest.mark.asyncio
    async def test_print_mode_subprocess(self, agent):
        await agent.start()

        with patch.object(agent, "_run_subprocess", return_value="I recommend testing."):
            msg = await agent.send_and_wait("What to test?")

        assert msg.source == "gemini"
        assert msg.role == MessageRole.OPINION
        assert "testing" in msg.content

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

        with patch.object(agent, "_run_subprocess", return_value="[Error: exit code 1]"):
            msg = await agent.send_and_wait("test")

        assert "Error" in msg.content


class TestGeminiBuildPrompt:
    def test_includes_completion_marker(self, agent):
        prompt = agent._build_prompt("What framework?")
        assert COMPLETION_MARKER in prompt
        assert "What framework" in prompt

    def test_includes_role(self, agent):
        prompt = agent._build_prompt("Test")
        assert "[System Role]" in prompt
        assert "Reviewer" in prompt


class TestGeminiExtractResponse:
    def test_strips_marker(self, agent):
        raw = f"Some response {COMPLETION_MARKER}\n> "
        result = agent._extract_response(raw)
        assert COMPLETION_MARKER not in result
        assert "Some response" in result

    def test_handles_empty(self, agent):
        result = agent._extract_response("")
        assert isinstance(result, str)


class TestGeminiParseUsage:
    def test_token_count_pattern(self, agent):
        result = agent._parse_usage_from_output("Response\nToken count: 5000")
        assert result["used"] == 5000

    def test_usage_pattern(self, agent):
        result = agent._parse_usage_from_output("Response\nUsage: 3000")
        assert result["usage"]["used"] == 3000 if "usage" in result else result["used"] == 3000

    def test_no_usage(self, agent):
        result = agent._parse_usage_from_output("Just a response")
        assert result["used"] == 0

    def test_input_output_tokens(self, agent):
        result = agent._parse_usage_from_output(
            'Response\ninput_tokens: 100 output_tokens: 50'
        )
        assert result["used"] == 150


class TestGeminiIsAlive:
    @pytest.mark.asyncio
    async def test_alive_after_start(self, agent):
        await agent.start()
        assert await agent.is_alive() is True

    @pytest.mark.asyncio
    async def test_not_alive_after_shutdown(self, agent):
        await agent.start()
        await agent.graceful_shutdown()
        assert await agent.is_alive() is False


class TestGeminiGetContextUsage:
    @pytest.mark.asyncio
    async def test_returns_usage(self, agent):
        usage = await agent.get_context_usage()
        assert isinstance(usage, ContextUsage)
        assert usage.total == 1_000_000
