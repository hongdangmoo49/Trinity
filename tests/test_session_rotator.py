"""Tests for trinity.context.rotator — SessionRotator."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from trinity.agents.base import AgentWrapper
from trinity.context.rotator import SessionRotator
from trinity.context.shared import SharedContextEngine
from trinity.models import AgentSpec, DeliberationMessage, MessageRole, Provider


def _make_mock_agent(name: str) -> MagicMock:
    agent = MagicMock(spec=AgentWrapper)
    agent.name = name
    agent.spec = AgentSpec(
        name=name,
        provider=Provider.CLAUDE_CODE,
        cli_command="claude",
        role_prompt=f"You are {name}.",
    )
    agent.start = AsyncMock()
    agent.send_and_wait = AsyncMock()
    agent.graceful_shutdown = AsyncMock()
    return agent


@pytest.fixture
def shared_engine(tmp_path):
    return SharedContextEngine(
        path=tmp_path / "shared.md",
        keep_sections=["## Current Goal", "## Agreed Conclusion"],
    )


@pytest.fixture
def agents():
    return {
        "claude": _make_mock_agent("claude"),
        "codex": _make_mock_agent("codex"),
    }


@pytest.fixture
def rotator(agents, shared_engine):
    return SessionRotator(
        agents=agents,
        shared=shared_engine,
        recent_rounds=3,
    )


class TestSessionRotatorRotate:
    @pytest.mark.asyncio
    async def test_full_rotation_flow(self, rotator, agents, shared_engine):
        # Setup: agent returns a summary
        agents["claude"].send_and_wait = AsyncMock(
            return_value=DeliberationMessage(
                source="claude",
                target="all",
                round_num=0,
                role=MessageRole.SUMMARY,
                content="## 완료\n- Auth 설계 완료\n## 다음 단계\n- 구현",
            )
        )

        shared_engine.initialize("Build auth", ["claude", "codex"])

        result = await rotator.rotate("claude")

        assert result is True
        agents["claude"].send_and_wait.assert_called_once()  # Summary request
        agents["claude"].graceful_shutdown.assert_called_once()  # Shutdown
        agents["claude"].start.assert_called_once()  # Restart

    @pytest.mark.asyncio
    async def test_summary_saved_to_shared(self, rotator, agents, shared_engine):
        agents["claude"].send_and_wait = AsyncMock(
            return_value=DeliberationMessage(
                source="claude",
                target="all",
                round_num=0,
                role=MessageRole.SUMMARY,
                content="Summary of work done.",
            )
        )

        shared_engine.initialize("Test goal", ["claude"])
        await rotator.rotate("claude")

        # Session history should be in shared.md
        history = shared_engine.read_section("Session History")
        assert history is not None
        assert "claude" in history
        assert "Summary of work done" in history

    @pytest.mark.asyncio
    async def test_continuation_includes_role(self, rotator, agents, shared_engine):
        agents["claude"].send_and_wait = AsyncMock(
            return_value=DeliberationMessage(
                source="claude", target="all", round_num=0,
                role=MessageRole.SUMMARY, content="Summary",
            )
        )

        shared_engine.initialize("Test", ["claude"])
        await rotator.rotate("claude")

        # Check that start was called with a continuation prompt
        call_args = agents["claude"].start.call_args
        initial_prompt = call_args[1].get("initial_prompt", "")
        assert "이전 세션에서 이어서" in initial_prompt
        # role_prompt is "You are claude." since spec uses name as fallback
        assert "claude" in initial_prompt

    @pytest.mark.asyncio
    async def test_rotation_failure_recovers(self, rotator, agents):
        # Agent fails during summary request
        agents["claude"].send_and_wait = AsyncMock(
            side_effect=RuntimeError("Agent crashed")
        )

        result = await rotator.rotate("claude")

        # Should return False but try to restart
        assert result is False
        agents["claude"].start.assert_called()  # Recovery attempt

    @pytest.mark.asyncio
    async def test_nonexistent_agent_returns_false(self, rotator):
        result = await rotator.rotate("nonexistent")
        assert result is False


class TestSessionRotatorTracking:
    @pytest.mark.asyncio
    async def test_rotation_count(self, rotator, agents, shared_engine):
        agents["claude"].send_and_wait = AsyncMock(
            return_value=DeliberationMessage(
                source="claude", target="all", round_num=0,
                role=MessageRole.SUMMARY, content="Summary",
            )
        )

        shared_engine.initialize("Test", ["claude"])

        await rotator.rotate("claude")
        assert rotator.get_rotation_count("claude") == 1

        await rotator.rotate("claude")
        assert rotator.get_rotation_count("claude") == 2

    def test_no_rotation_count_initially(self, rotator):
        assert rotator.get_rotation_count("claude") == 0

    def test_get_all_rotation_counts(self, rotator):
        rotator._rotation_count = {"claude": 2, "codex": 1}
        counts = rotator.get_all_rotation_counts()
        assert counts == {"claude": 2, "codex": 1}


class TestSessionRotatorBroadcast:
    def test_broadcast_message(self, rotator):
        rotator._rotation_count = {"claude": 2}
        msg = rotator.build_broadcast_message("claude")
        assert "claude" in msg
        assert "세션이 교체" in msg
        assert "2" in msg  # rotation count

    def test_broadcast_first_rotation(self, rotator):
        msg = rotator.build_broadcast_message("claude")
        assert "0" in msg  # No rotation yet
