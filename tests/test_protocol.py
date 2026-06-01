"""Tests for trinity.deliberation.protocol — DeliberationProtocol."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from trinity.agents.base import AgentWrapper
from trinity.config import TrinityConfig
from trinity.context.shared import SharedContextEngine
from trinity.deliberation.consensus import ConsensusEngine
from trinity.deliberation.distributor import TaskDistributor
from trinity.deliberation.protocol import DeliberationProtocol
from trinity.models import (
    AgentSpec,
    ConsensusResult,
    ContextUsage,
    DeliberationMessage,
    DeliberationResult,
    MessageRole,
    Provider,
)


def _make_mock_agent(name: str) -> MagicMock:
    """Create a mock AgentWrapper with sensible defaults."""
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
    """Create a test DeliberationMessage."""
    return DeliberationMessage(
        source=name,
        target="all",
        round_num=round_num,
        role=MessageRole.OPINION,
        content=content,
    )


class TestBuildRoundPrompt:
    """Test _build_round_prompt generates correct prompts."""

    def test_round_1_prompt(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {"claude": _make_mock_agent("claude")}
        protocol = DeliberationProtocol(
            agents=agents, shared=engine, max_rounds=5,
        )
        prompt = protocol._build_round_prompt(1, "What framework to use?")
        assert "What framework to use?" in prompt
        assert "initial opinion" in prompt.lower()

    def test_round_2_prompt_includes_previous(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {"claude": _make_mock_agent("claude")}
        protocol = DeliberationProtocol(
            agents=agents, shared=engine, max_rounds=5,
        )
        # Simulate Round 1 opinions in shared.md
        engine.initialize("Test goal", ["claude"])
        engine.append_opinion("claude", 1, "I think we should use JWT.")

        prompt = protocol._build_round_prompt(2, "What framework?")
        assert "Previous round opinions" in prompt
        assert "JWT" in prompt
        assert "AGREE or DISAGREE" in prompt

    def test_round_2_prompt_fallback_when_no_prev(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {"claude": _make_mock_agent("claude")}
        protocol = DeliberationProtocol(
            agents=agents, shared=engine, max_rounds=5,
        )
        engine.initialize("Test", ["claude"])
        # Don't add any opinions for round 1

        prompt = protocol._build_round_prompt(2, "Test")
        assert "not available" in prompt


class TestCollectOpinions:
    """Test _collect_opinions parallel collection."""

    @pytest.mark.asyncio
    async def test_collects_from_all_agents(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {
            "claude": _make_mock_agent("claude"),
            "codex": _make_mock_agent("codex"),
        }

        # Mock send_and_wait
        agents["claude"].send_and_wait = AsyncMock(
            return_value=_make_opinion("claude", 1, "I agree with JWT.")
        )
        agents["codex"].send_and_wait = AsyncMock(
            return_value=_make_opinion("codex", 1, "Sessions are better.")
        )

        protocol = DeliberationProtocol(
            agents=agents, shared=engine, max_rounds=5,
        )

        opinions = await protocol._collect_opinions(1, "Test prompt")

        assert "claude" in opinions
        assert "codex" in opinions
        assert opinions["claude"].content == "I agree with JWT."
        assert opinions["codex"].content == "Sessions are better."

    @pytest.mark.asyncio
    async def test_handles_agent_exception(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {
            "claude": _make_mock_agent("claude"),
            "codex": _make_mock_agent("codex"),
        }

        agents["claude"].send_and_wait = AsyncMock(
            return_value=_make_opinion("claude", 1, "My opinion.")
        )
        agents["codex"].send_and_wait = AsyncMock(
            side_effect=RuntimeError("Codex crashed")
        )

        protocol = DeliberationProtocol(
            agents=agents, shared=engine, max_rounds=5,
        )

        opinions = await protocol._collect_opinions(1, "Test")

        assert "claude" in opinions
        assert "codex" in opinions
        assert "Error" in opinions["codex"].content
        assert "Codex crashed" in opinions["codex"].content

    @pytest.mark.asyncio
    async def test_sets_round_num_on_messages(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {"claude": _make_mock_agent("claude")}

        agents["claude"].send_and_wait = AsyncMock(
            return_value=_make_opinion("claude", 0, "Opinion")  # round 0 from agent
        )

        protocol = DeliberationProtocol(
            agents=agents, shared=engine, max_rounds=5,
        )

        opinions = await protocol._collect_opinions(3, "Test")
        assert opinions["claude"].round_num == 3


class TestProtocolRun:
    """Test full protocol.run() loop."""

    @pytest.mark.asyncio
    async def test_consensus_on_first_round(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {
            "claude": _make_mock_agent("claude"),
            "codex": _make_mock_agent("codex"),
        }

        agents["claude"].send_and_wait = AsyncMock(
            return_value=_make_opinion("claude", 1, "I agree with this approach.")
        )
        agents["codex"].send_and_wait = AsyncMock(
            return_value=_make_opinion("codex", 1, "I agree too.")
        )

        protocol = DeliberationProtocol(
            agents=agents, shared=engine, max_rounds=5,
        )
        result = await protocol.run("What framework?")

        assert result.has_consensus
        assert result.rounds_completed == 1

    @pytest.mark.asyncio
    async def test_consensus_requires_multiple_rounds(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {
            "claude": _make_mock_agent("claude"),
            "codex": _make_mock_agent("codex"),
        }

        # Round 1: no "agree" keyword → no consensus
        # Round 2+: both include "agree" → consensus
        call_count = {"n": 0}

        async def mock_send_claude(prompt, timeout=120.0):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return _make_opinion("claude", 1, "I think we should use JWT.")
            return _make_opinion("claude", 2, "I agree with sessions.")

        async def mock_send_codex(prompt, timeout=120.0):
            call_count["n"] += 1
            if call_count["n"] == 2:  # First call for codex (round 1)
                return _make_opinion("codex", 1, "Sessions are better.")
            return _make_opinion("codex", 2, "I agree with JWT.")

        agents["claude"].send_and_wait = mock_send_claude
        agents["codex"].send_and_wait = mock_send_codex

        protocol = DeliberationProtocol(
            agents=agents,
            shared=engine,
            max_rounds=5,
        )
        result = await protocol.run("Test prompt")

        # Round 1: neither has "agree" keyword → no consensus
        # Round 2: both include "agree" → consensus (2/2 ≥ 0.6)
        assert result.rounds_completed == 2
        assert result.has_consensus

    @pytest.mark.asyncio
    async def test_forced_conclusion_at_max_rounds(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {"claude": _make_mock_agent("claude")}

        agents["claude"].send_and_wait = AsyncMock(
            return_value=_make_opinion("claude", 1, "I think option A is best.")
        )

        # Consensus engine that always returns False
        class NeverConsensus(ConsensusEngine):
            def evaluate(self, opinions):
                return ConsensusResult(
                    reached=False,
                    agreement_count=0,
                    total_agents=1,
                    opinions=opinions,
                    summary="No consensus.",
                )

        protocol = DeliberationProtocol(
            agents=agents,
            shared=engine,
            consensus_engine=NeverConsensus(),
            max_rounds=3,
        )
        result = await protocol.run("Test")

        # Should force consensus at round 3
        assert result.rounds_completed == 3
        assert result.consensus.reached  # Forced
        assert "Forced conclusion" in result.consensus.summary

    @pytest.mark.asyncio
    async def test_task_distribution_after_consensus(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {
            "claude": _make_mock_agent("claude"),
        }

        agents["claude"].send_and_wait = AsyncMock(
            return_value=_make_opinion("claude", 1, "I agree with the plan.")
        )

        protocol = DeliberationProtocol(
            agents=agents, shared=engine, max_rounds=5,
        )
        result = await protocol.run("Test")

        assert len(result.tasks) == 1
        assert result.tasks[0].agent_name == "claude"

    @pytest.mark.asyncio
    async def test_writes_to_shared_context(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {"claude": _make_mock_agent("claude")}

        agents["claude"].send_and_wait = AsyncMock(
            return_value=_make_opinion("claude", 1, "I agree.")
        )

        protocol = DeliberationProtocol(
            agents=agents, shared=engine, max_rounds=5,
        )
        await protocol.run("What framework?")

        # shared.md should have been populated
        content = engine.read()
        assert "What framework?" in content
        assert "I agree" in content
        assert "Task Assignment" in content

    @pytest.mark.asyncio
    async def test_duration_and_tokens_tracked(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {"claude": _make_mock_agent("claude")}
        agents["claude"].context_usage = ContextUsage(used=500, total=200_000)

        agents["claude"].send_and_wait = AsyncMock(
            return_value=_make_opinion("claude", 1, "I agree.")
        )

        protocol = DeliberationProtocol(
            agents=agents, shared=engine, max_rounds=5,
        )
        result = await protocol.run("Test")

        assert result.duration_seconds > 0
        assert result.total_tokens_used == 500
