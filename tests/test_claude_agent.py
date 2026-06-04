"""Tests for trinity.agents.claude_agent — PrintModeClaudeAgent."""

import pytest
from unittest.mock import AsyncMock

from trinity.agents.claude_agent import PrintModeClaudeAgent
from trinity.models import AgentSpec, ContextUsage, MessageRole, Provider, ResponseStatus
from trinity.providers.invoker import ProviderTurnResult


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

    def test_context_usage_uses_selected_model_budget(self, claude_spec):
        claude_spec.model = "opus[1m]"
        claude_spec.context_budget = 0
        agent = PrintModeClaudeAgent(claude_spec)
        assert agent.context_usage.total == 1_000_000

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
    async def test_invokes_provider_request(self, agent):
        await agent.start()

        mock_result = ProviderTurnResult(
            agent_name="claude",
            content="I recommend JWT.",
            raw_output='{"result":"I recommend JWT."}',
            status=ResponseStatus.OK,
            elapsed_seconds=0.25,
            usage=ContextUsage(used=150, total=0),
            metadata={"model": "claude-sonnet-4-6"},
        )

        agent._invoker.invoke = AsyncMock(return_value=mock_result)
        msg = await agent.send_and_wait("What auth method?")

        request = agent._invoker.invoke.call_args.args[0]
        assert request.agent_name == "claude"
        assert request.role_prompt == "You are the Architect."
        assert request.context_prompt == ""
        assert request.extra_args == ("--dangerously-skip-permissions",)
        assert msg.source == "claude"
        assert msg.target == "all"
        assert msg.role == MessageRole.OPINION
        assert msg.content == "I recommend JWT."
        assert msg.metadata["token_count"] == 150
        assert msg.metadata["model"] == "claude-sonnet-4-6"
        assert msg.metadata["response_status"] == "ok"

    @pytest.mark.asyncio
    async def test_updates_context_usage(self, agent):
        await agent.start()

        agent._invoker.invoke = AsyncMock(
            return_value=ProviderTurnResult(
                agent_name="claude",
                content="Response",
                raw_output="raw",
                status=ResponseStatus.OK,
                elapsed_seconds=0.1,
                usage=ContextUsage(used=300, total=0),
            )
        )
        await agent.send_and_wait("test")

        assert agent.context_usage.used == 300
        assert agent.context_usage.total == 200_000

    @pytest.mark.asyncio
    async def test_timeout_returns_error_message(self, agent):
        await agent.start()

        agent._invoker.invoke = AsyncMock(
            return_value=ProviderTurnResult(
                agent_name="claude",
                content="[Timeout after 120s]",
                raw_output="",
                status=ResponseStatus.TIMEOUT,
                elapsed_seconds=120,
                diagnostics=["Provider invocation timed out."],
            )
        )
        msg = await agent.send_and_wait("test", timeout=120)

        assert "Timeout" in msg.content
        assert msg.metadata["response_status"] == "timeout"

    @pytest.mark.asyncio
    async def test_increments_message_count(self, agent):
        await agent.start()

        agent._invoker.invoke = AsyncMock(
            return_value=ProviderTurnResult(
                agent_name="claude",
                content="ok",
                raw_output="raw",
                status=ResponseStatus.OK,
                elapsed_seconds=0.1,
            )
        )
        await agent.send_and_wait("test1")
        await agent.send_and_wait("test2")

        assert agent._message_count == 2


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
