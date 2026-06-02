"""Tests for prompt compression integration in DeliberationProtocol."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock

from trinity.agents.base import AgentWrapper
from trinity.context.shared import SharedContextEngine
from trinity.deliberation.protocol import DeliberationProtocol
from trinity.models import AgentSpec, ContextUsage, DeliberationMessage, MessageRole, Provider


def _make_mock_agent(name: str, response: str = "OK"):
    """Create a minimal mock agent for testing."""
    spec = AgentSpec(name=name, provider=Provider.CLAUDE_CODE, cli_command="claude")
    agent = AsyncMock(spec=AgentWrapper)
    agent.spec = spec
    agent.name = name
    agent.context_usage = ContextUsage(used=0, total=200_000)

    async def mock_send(prompt, timeout=120.0):
        return DeliberationMessage(
            source=name,
            target="all",
            round_num=0,
            role=MessageRole.OPINION,
            content=response,
        )

    agent.send_and_wait = mock_send
    agent.start = AsyncMock()
    agent.graceful_shutdown = AsyncMock()
    agent.get_context_usage = AsyncMock(return_value=ContextUsage(used=0, total=200_000))
    agent.is_alive = AsyncMock(return_value=True)
    return agent


class TestRoundPromptCompression:

    def test_round_1_no_compression(self, tmp_path):
        """Round 1 prompt should not reference any previous round."""
        shared = SharedContextEngine(path=tmp_path / "shared.md")
        agent = _make_mock_agent("claude")
        protocol = DeliberationProtocol(
            agents={"claude": agent},
            shared=shared,
            max_rounds=5,
        )

        shared.initialize(goal="Design auth system", agent_names=["claude"])
        prompt = protocol._build_round_prompt(1, "Design auth system")

        assert "Design auth system" in prompt
        assert "Previous round" not in prompt

    def test_round_2_verbatim_previous(self, tmp_path):
        """Round 2 should include Round 1 verbatim (no compression yet)."""
        shared = SharedContextEngine(path=tmp_path / "shared.md")
        agent = _make_mock_agent("claude")
        protocol = DeliberationProtocol(
            agents={"claude": agent},
            shared=shared,
            max_rounds=5,
        )

        shared.initialize(goal="test", agent_names=["claude"])
        shared.append_opinion("claude", 1, "I recommend pytest for testing.")

        prompt = protocol._build_round_prompt(2, "test")
        assert "pytest" in prompt

    def test_round_3_uses_compressed_old_rounds(self, tmp_path):
        """Round 3+ should use compressed summaries for rounds older than N-1."""
        shared = SharedContextEngine(path=tmp_path / "shared.md")
        agent = _make_mock_agent("claude")
        protocol = DeliberationProtocol(
            agents={"claude": agent},
            shared=shared,
            max_rounds=5,
            compression_enabled=True,
            compression_round_threshold=2,
        )

        shared.initialize(goal="test", agent_names=["claude"])
        shared.append_opinion("claude", 1, "Round 1 opinion with detailed analysis. " * 20)
        shared.append_opinion("claude", 2, "Round 2 opinion.")
        shared.write_compressed_summary(1, "Compressed: claude recommends pytest")

        prompt = protocol._build_round_prompt(3, "test")
        assert "Compressed: claude recommends pytest" in prompt
        assert "Round 2 opinion" in prompt

    def test_compression_disabled(self, tmp_path):
        """When compression_enabled=False, all rounds should be verbatim."""
        shared = SharedContextEngine(path=tmp_path / "shared.md")
        agent = _make_mock_agent("claude")
        protocol = DeliberationProtocol(
            agents={"claude": agent},
            shared=shared,
            max_rounds=5,
            compression_enabled=False,
        )

        shared.initialize(goal="test", agent_names=["claude"])
        shared.append_opinion("claude", 1, "Opinion R1.")
        shared.append_opinion("claude", 2, "Opinion R2.")
        shared.write_compressed_summary(1, "Compressed R1")

        prompt = protocol._build_round_prompt(3, "test")
        assert "Compressed R1" not in prompt

    def test_compressed_round_opinions_removed(self, tmp_path):
        """After compression, original Round N Opinions section should be removed."""
        shared = SharedContextEngine(path=tmp_path / "shared.md")
        agent = _make_mock_agent("claude")
        protocol = DeliberationProtocol(
            agents={"claude": agent},
            shared=shared,
            max_rounds=5,
            compression_enabled=True,
            compression_round_threshold=2,
        )

        shared.initialize(goal="test", agent_names=["claude"])
        shared.append_opinion("claude", 1, "Original opinion round 1. " * 30)
        shared.append_opinion("claude", 2, "Opinion round 2.")

        # Before: both sections exist
        assert shared.read_section("Round 1 Opinions") is not None
        assert shared.read_section("Round 2 Opinions") is not None

        # Trigger compression
        protocol._build_round_prompt(3, "test")

        # After: R1 Opinions removed, R1 Summary exists, R2 Opinions preserved
        assert shared.read_section("Round 1 Opinions") is None
        assert shared.read_section("Round 1 Summary") is not None
        assert shared.read_section("Round 2 Opinions") is not None

    def test_prompt_size_reduction(self, tmp_path):
        """Verify that compression reduces context from old rounds.

        Compare the full verbatim context (all rounds) vs the compressed
        version (old rounds summarized, recent round verbatim).
        """
        shared = SharedContextEngine(path=tmp_path / "shared.md")
        agent = _make_mock_agent("claude")
        long_opinion = "This is a detailed analysis with important details. " * 50

        shared.initialize(goal="test", agent_names=["claude"])
        shared.append_opinion("claude", 1, long_opinion)
        shared.append_opinion("claude", 2, long_opinion)
        shared.append_opinion("claude", 3, long_opinion)
        shared.write_compressed_summary(1, "claude: recommends approach A")
        shared.write_compressed_summary(2, "claude: agrees with approach A")

        protocol_compressed = DeliberationProtocol(
            agents={"claude": agent},
            shared=shared,
            max_rounds=5,
            compression_enabled=True,
        )
        prompt_compressed = protocol_compressed._build_round_prompt(4, "test")

        # Build what the full verbatim context would be (all rounds unsummarized)
        r1 = shared.read_section("Round 1 Opinions")
        r2 = shared.read_section("Round 2 Opinions")
        r3 = shared.read_section("Round 3 Opinions")
        full_verbatim = f"{r1}\n\n{r2}\n\n{r3}"

        # The compressed prompt's context portion should be smaller than
        # the full verbatim of all rounds
        assert len(prompt_compressed) < len(full_verbatim)

    def test_budget_checker_integrated(self, tmp_path):
        """Protocol should have a budget_checker attribute."""
        shared = SharedContextEngine(path=tmp_path / "shared.md")
        agent = _make_mock_agent("claude")
        protocol = DeliberationProtocol(
            agents={"claude": agent},
            shared=shared,
            max_rounds=5,
        )

        shared.initialize(goal="test", agent_names=["claude"])
        agent.context_usage = ContextUsage(used=110_000, total=200_000)
        shared.append_opinion("claude", 1, "Opinion. " * 2000)

        assert protocol.budget_checker is not None
        prompt = protocol._build_round_prompt(2, "test")
        result = protocol.budget_checker.check(
            prompt=prompt,
            current_usage=agent.context_usage,
            agent_spec=agent.spec,
        )
        assert result.recommendation in ("proceed", "proceed_with_caution", "rotate_first")
