"""Tests for Antigravity print-mode agent."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from trinity.agents.antigravity_agent import AntigravityPrintAgent
from trinity.models import AgentSpec, Provider, ResponseStatus
from trinity.providers.invoker import ProviderTurnResult
from trinity.providers.policy import ExecutionAuthority


@pytest.fixture
def antigravity_spec():
    return AgentSpec(
        name="antigravity",
        provider=Provider.ANTIGRAVITY_CLI,
        cli_command="agy",
        role_prompt="You are the Reviewer.",
    )


@pytest.mark.asyncio
async def test_send_and_wait_returns_deliberation_message(antigravity_spec):
    agent = AntigravityPrintAgent(antigravity_spec)
    agent._invoker.invoke = AsyncMock(
        return_value=ProviderTurnResult(
            agent_name="antigravity",
            content="Reviewed.",
            raw_output="Reviewed.\n",
            status=ResponseStatus.OK,
            elapsed_seconds=1.25,
            execution_authority=ExecutionAuthority.PROVIDER_MANAGED,
            metadata={"output_format": "plain-text"},
        )
    )

    await agent.start("Shared context.")
    message = await agent.send_and_wait("Check this.", timeout=30)

    assert message.source == "antigravity"
    assert message.content == "Reviewed."
    assert message.metadata["response_status"] == "ok"
    assert message.metadata["output_format"] == "plain-text"
    agent._invoker.invoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_before_start_raises(antigravity_spec):
    agent = AntigravityPrintAgent(antigravity_spec)

    with pytest.raises(RuntimeError, match="not started"):
        await agent.send_and_wait("Check this.")
