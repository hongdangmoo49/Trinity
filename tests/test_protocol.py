"""Tests for trinity.deliberation.protocol — DeliberationProtocol."""

import logging
import pytest
from rich.console import Console
from unittest.mock import AsyncMock, MagicMock

from trinity.agents.base import AgentWrapper
from trinity.config import TrinityConfig
from trinity.context.budget import BudgetCheckResult
from trinity.context.shared import SharedContextEngine
from trinity.deliberation.consensus import ConsensusEngine
from trinity.deliberation.protocol import DeliberationProtocol
from trinity.deliberation.synthesis import SynthesisInput, SynthesisResult
from trinity.models import (
    AgentSpec,
    ConsensusResult,
    ContextUsage,
    DeliberationMessage,
    MessageRole,
    Provider,
)
from trinity.tui.app import AgentTUIState, TrinityTUI
from trinity.tui.events import TUIEvent, TUIEventType


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


def _make_opinion(
    name: str,
    round_num: int,
    content: str,
    metadata: dict | None = None,
) -> DeliberationMessage:
    """Create a test DeliberationMessage."""
    return DeliberationMessage(
        source=name,
        target="all",
        round_num=round_num,
        role=MessageRole.OPINION,
        content=content,
        metadata=metadata or {},
    )


class RecordingBudgetChecker:
    """Budget checker test double that records call order."""

    def __init__(self, events: list[str]):
        self.events = events
        self.calls: list[tuple[str, str, ContextUsage]] = []

    def check(
        self,
        prompt: str,
        current_usage: ContextUsage,
        agent_spec: AgentSpec,
    ) -> BudgetCheckResult:
        self.events.append(f"check:{agent_spec.name}")
        self.calls.append((prompt, agent_spec.name, current_usage))
        return BudgetCheckResult(
            estimated_prompt_tokens=10,
            projected_total=current_usage.used + 10,
            projected_ratio=0.01,
            safe=True,
            recommendation="proceed",
        )


class RecordingSynthesisAgent:
    """Synthesis test double that records received round input."""

    def __init__(self):
        self.inputs: list[SynthesisInput] = []

    async def synthesize(self, synthesis_input: SynthesisInput) -> SynthesisResult:
        self.inputs.append(synthesis_input)
        consensus = ConsensusResult(
            reached=True,
            agreement_count=len(synthesis_input.opinions),
            total_agents=len(synthesis_input.opinions),
            opinions=dict(synthesis_input.opinions),
            summary="Recorded synthesis consensus.",
        )
        return SynthesisResult(
            round_num=synthesis_input.round_num,
            consensus_reached=True,
            agreement_count=consensus.agreement_count,
            total_agents=consensus.total_agents,
            summary_for_shared_md=consensus.summary,
            consensus=consensus,
            source="test-synthesis",
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

    def test_korean_prompt_requires_korean_user_facing_output(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {"codex": _make_mock_agent("codex")}
        protocol = DeliberationProtocol(
            agents=agents,
            shared=engine,
            max_rounds=5,
            lang="ko",
        )

        prompt = protocol._build_round_prompt(1, "레이어2 브릿지 봇을 설계해라")

        assert "반드시 한국어" in prompt
        assert "영어로 된 사용자-facing 문장" in prompt
        assert "VOTE: APPROVE" in prompt


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

    @pytest.mark.asyncio
    async def test_invalid_response_goes_to_diagnostics_not_opinions(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        engine.initialize("Test goal", ["antigravity"])
        agents = {"antigravity": _make_mock_agent("antigravity")}

        agents["antigravity"].send_and_wait = AsyncMock(
            return_value=_make_opinion(
                "antigravity",
                0,
                "Waiting for authentication...\nOpen the following URL to login.",
            )
        )

        consensus = ConsensusEngine(required_fraction=1.0)
        protocol = DeliberationProtocol(
            agents=agents,
            shared=engine,
            consensus_engine=consensus,
            max_rounds=1,
        )

        result = await protocol.run("Test prompt")

        assert result.rounds_completed == 1
        assert result.consensus is not None
        assert not result.has_consensus
        assert result.consensus.total_agents == 0
        assert result.consensus.opinions == {}
        assert "No usable consensus" in result.consensus.summary
        assert "Majority opinion selected" not in result.consensus.summary
        assert engine.read_section("Round 1 Opinions") is None
        diagnostics = engine.read_section("Response Diagnostics")
        assert diagnostics is not None
        assert "classification: auth_wait" in diagnostics
        assert "Waiting for authentication" in diagnostics

    @pytest.mark.asyncio
    async def test_invalid_response_excluded_from_consensus_denominator(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {
            "claude": _make_mock_agent("claude"),
            "antigravity": _make_mock_agent("antigravity"),
        }

        agents["claude"].send_and_wait = AsyncMock(
            return_value=_make_opinion("claude", 1, "I agree with the plan.")
        )
        agents["antigravity"].send_and_wait = AsyncMock(
            return_value=_make_opinion(
                "antigravity",
                1,
                "Waiting for authentication...\nOpen the following URL to login.",
            )
        )

        protocol = DeliberationProtocol(
            agents=agents,
            shared=engine,
            consensus_engine=ConsensusEngine(required_fraction=1.0),
            max_rounds=1,
        )

        result = await protocol.run("Test prompt")

        assert result.has_consensus
        assert result.consensus.agreement_count == 1
        assert result.consensus.total_agents == 1
        assert result.consensus.opinions == {"claude": "I agree with the plan."}

        assert engine.read_section("Round 1 Opinions") is None
        round_responses = engine.read_section("Round 1 Responses")
        assert round_responses is not None
        assert "claude" in round_responses
        assert "antigravity" in round_responses
        assert "clean_output_path" in round_responses

    @pytest.mark.asyncio
    async def test_budget_checker_runs_before_agent_sends(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {
            "claude": _make_mock_agent("claude"),
            "codex": _make_mock_agent("codex"),
        }
        events: list[str] = []

        def make_send(name: str):
            def send_and_wait(prompt, timeout=120.0):
                events.append(f"send:{name}")

                async def response():
                    return _make_opinion(name, 1, "I agree.")

                return response()

            return send_and_wait

        agents["claude"].send_and_wait = make_send("claude")
        agents["codex"].send_and_wait = make_send("codex")

        protocol = DeliberationProtocol(
            agents=agents, shared=engine, max_rounds=5,
        )
        protocol.budget_checker = RecordingBudgetChecker(events)

        await protocol._collect_opinions(1, "Test prompt")

        assert events[:2] == ["check:claude", "check:codex"]
        assert events[2:] == ["send:claude", "send:codex"]
        assert protocol.last_round_rotation_candidates == []

    @pytest.mark.asyncio
    async def test_high_risk_agents_are_surfaced_before_send(self, tmp_path, caplog):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {
            "claude": _make_mock_agent("claude"),
            "codex": _make_mock_agent("codex"),
        }
        agents["claude"].context_usage = ContextUsage(used=119_000, total=200_000)
        agents["codex"].context_usage = ContextUsage(used=20_000, total=200_000)

        agents["claude"].send_and_wait = AsyncMock(
            return_value=_make_opinion("claude", 1, "I agree.")
        )
        agents["codex"].send_and_wait = AsyncMock(
            return_value=_make_opinion("codex", 1, "I agree.")
        )

        protocol = DeliberationProtocol(
            agents=agents, shared=engine, max_rounds=5,
        )

        with caplog.at_level(logging.WARNING, logger="trinity.deliberation.protocol"):
            await protocol._collect_opinions(1, "x " * 1000)

        assert [w.agent_name for w in protocol.last_round_rotation_candidates] == [
            "claude"
        ]
        candidate = protocol.last_round_rotation_candidates[0]
        assert candidate.round_num == 1
        assert candidate.current_used == 119_000
        assert candidate.context_total == 200_000
        assert candidate.projected_total > candidate.current_used
        assert candidate.recommendation == "rotate_first"
        assert candidate.safe is False
        assert protocol.get_agents_needing_rotation() == [candidate]
        assert protocol.get_rotation_candidates() == [candidate]
        assert "Rotation should run before the next prompt" in caplog.text

    @pytest.mark.asyncio
    async def test_unreliable_response_metadata_is_emitted(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {"claude": _make_mock_agent("claude")}
        events = []

        agents["claude"].send_and_wait = AsyncMock(
            return_value=_make_opinion(
                "claude",
                1,
                "I agree with the plan.",
                metadata={"completed": False},
            )
        )

        protocol = DeliberationProtocol(
            agents=agents,
            shared=engine,
            max_rounds=1,
            event_callback=events.append,
        )

        opinions = await protocol._collect_opinions(1, "Test prompt")

        assert protocol._is_unusable_agent_response(opinions["claude"])
        responded = [
            event for event in events if event.type == TUIEventType.AGENT_RESPONDED
        ][0]
        assert responded.data["response_status"] == "timeout"
        assert responded.data["metadata"]["completed"] is False
        assert responded.data["metadata"]["agent_response"]["status"] == "timeout"


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

        # Should not report a false majority consensus at round 3
        assert result.rounds_completed == 3
        assert not result.has_consensus
        assert not result.consensus.reached
        assert "Consensus not reached after 3 rounds" in result.consensus.summary
        assert "No majority consensus was selected" in result.consensus.summary
        assert "Majority opinion selected" not in result.consensus.summary
        assert result.tasks == []

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
        assert "Round 1 Synthesis" in content
        assert "Round 1 Responses" in content
        assert "clean_output_path" in content
        assert engine.read_section("Round 1 Opinions") is None
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

    @pytest.mark.asyncio
    async def test_structured_blueprint_metadata_attached(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {"claude": _make_mock_agent("claude")}
        agents["claude"].send_and_wait = AsyncMock(
            return_value=_make_opinion(
                "claude",
                1,
                """\
BLUEPRINT:
Title: Route Bot
Summary: Finds bridge routes.

Architecture:
- Quote Collector: collects quotes

Data Flow:
- request -> quotes -> score

Acceptance Criteria:
- returns ranked paths

VOTE: APPROVE
""",
            )
        )

        protocol = DeliberationProtocol(
            agents=agents,
            shared=engine,
            max_rounds=3,
        )

        result = await protocol.run("Design route bot")

        structured = result.metadata["structured_consensus"]
        assert result.has_consensus
        assert structured["reached"] is True
        assert structured["final_blueprint"]["title"] == "Route Bot"

    @pytest.mark.asyncio
    async def test_protocol_uses_central_synthesis_agent(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {"claude": _make_mock_agent("claude")}
        agents["claude"].send_and_wait = AsyncMock(
            return_value=_make_opinion("claude", 1, "I agree with the plan.")
        )
        synthesis_agent = RecordingSynthesisAgent()

        protocol = DeliberationProtocol(
            agents=agents,
            shared=engine,
            max_rounds=3,
            synthesis_agent=synthesis_agent,
        )

        result = await protocol.run("Design route bot")

        assert result.has_consensus
        assert len(synthesis_agent.inputs) == 1
        synthesis_input = synthesis_agent.inputs[0]
        assert synthesis_input.user_prompt == "Design route bot"
        assert synthesis_input.round_num == 1
        assert synthesis_input.opinions == {"claude": "I agree with the plan."}
        assert result.metadata["synthesis"]["source"] == "test-synthesis"
        synthesis_section = engine.read_section("Round 1 Synthesis")
        assert synthesis_section is not None
        assert "Recorded synthesis consensus." in synthesis_section
        assert "source: test-synthesis" in synthesis_section

    @pytest.mark.asyncio
    async def test_structured_open_question_stops_round_loop(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        agents = {"antigravity": _make_mock_agent("antigravity")}
        agents["antigravity"].send_and_wait = AsyncMock(
            return_value=_make_opinion(
                "antigravity",
                1,
                """\
VOTE: BLOCKED_BY_QUESTION

OPEN QUESTIONS:
- Question: Optimize for cost or latency?
  Options: cost | latency | mixed
  Recommended: mixed
  Rationale: Trade-off changes scoring.
""",
            )
        )

        protocol = DeliberationProtocol(
            agents=agents,
            shared=engine,
            max_rounds=3,
        )

        result = await protocol.run("Design route bot")

        structured = result.metadata["structured_consensus"]
        assert result.rounds_completed == 1
        assert not result.has_consensus
        assert structured["open_questions"][0]["question"] == (
            "Optimize for cost or latency?"
        )
        assert structured["open_questions"][0]["options"] == [
            "cost",
            "latency",
            "mixed",
        ]
        assert structured["open_questions"][0]["recommended_option"] == "mixed"


class TestTUIResponseStatus:
    """Regression tests for protocol response metadata consumed by the TUI."""

    def test_timeout_response_event_marks_agent_error(self):
        config = TrinityConfig.default_config()
        tui = TrinityTUI(config, Console(force_terminal=True, width=120))
        tui.start_round(1)

        tui.consume_event(TUIEvent(
            type=TUIEventType.AGENT_RESPONDED,
            data={
                "agent": "claude",
                "content": "[Timeout after 120s]",
                "metadata": {"error": "timeout"},
                "round_num": 1,
            },
        ))

        assert tui.agents["claude"].state == AgentTUIState.ERROR
        assert tui.rounds[0].agent_states["claude"] == AgentTUIState.ERROR
        assert tui.agents["claude"].full_response == "[Timeout after 120s]"

    def test_captured_fallback_response_event_marks_agent_error(self):
        config = TrinityConfig.default_config()
        tui = TrinityTUI(config, Console(force_terminal=True, width=120))
        tui.start_round(1)

        tui.consume_event(TUIEvent(
            type=TUIEventType.AGENT_RESPONDED,
            data={
                "agent": "claude",
                "content": "Partial captured pane output",
                "metadata": {"detector": "fallback"},
                "round_num": 1,
            },
        ))

        assert tui.agents["claude"].state == AgentTUIState.ERROR
        assert tui.rounds[0].agent_states["claude"] == AgentTUIState.ERROR
