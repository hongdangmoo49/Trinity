"""Tests for central deliberation synthesis contracts."""

import pytest

from trinity.deliberation.synthesis import (
    FallbackSynthesisAgent,
    HeuristicSynthesisAgent,
    SynthesisInput,
    SynthesisResult,
)
from trinity.models import ConsensusResult


BLUEPRINT_TEXT = """\
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
"""


@pytest.mark.asyncio
async def test_heuristic_synthesis_reaches_structured_consensus():
    agent = HeuristicSynthesisAgent()

    result = await agent.synthesize(
        SynthesisInput(
            user_prompt="Design route bot",
            round_num=1,
            opinions={"claude": BLUEPRINT_TEXT},
        )
    )

    assert result.consensus_reached is True
    assert result.consensus is not None
    assert result.consensus.reached is True
    assert result.structured_consensus is not None
    assert result.recommended_blueprint is not None
    assert result.recommended_blueprint.title == "Route Bot"
    assert result.to_dict()["structured_consensus"]["reached"] is True


@pytest.mark.asyncio
async def test_heuristic_synthesis_surfaces_user_questions():
    agent = HeuristicSynthesisAgent()

    result = await agent.synthesize(
        SynthesisInput(
            user_prompt="Design route bot",
            round_num=1,
            opinions={
                "codex": """\
VOTE: BLOCKED_BY_QUESTION

OPEN QUESTIONS:
- Question: Optimize for cost or latency?
  Options: cost | latency | mixed
  Recommended: mixed
  Rationale: Changes route scoring.
"""
            },
        )
    )

    assert result.consensus_reached is False
    assert len(result.open_questions_for_user) == 1
    assert result.open_questions_for_user[0].question == (
        "Optimize for cost or latency?"
    )
    assert result.next_round_prompt == "Wait for user decisions before continuing."


@pytest.mark.asyncio
async def test_heuristic_synthesis_falls_back_to_keyword_consensus():
    agent = HeuristicSynthesisAgent()

    result = await agent.synthesize(
        SynthesisInput(
            user_prompt="Choose framework",
            round_num=1,
            opinions={
                "claude": "I agree with using pytest.",
                "codex": "I agree too.",
            },
        )
    )

    assert result.consensus_reached is True
    assert result.structured_consensus is not None
    assert result.structured_consensus.reached is False
    assert result.consensus is not None
    assert result.consensus.summary.startswith("Consensus reached")


class BrokenSynthesisAgent:
    async def synthesize(self, synthesis_input: SynthesisInput) -> SynthesisResult:
        raise RuntimeError("provider synthesis unavailable")


class StaticFallbackAgent:
    async def synthesize(self, synthesis_input: SynthesisInput) -> SynthesisResult:
        consensus = ConsensusResult(
            reached=True,
            agreement_count=1,
            total_agents=1,
            opinions={"fallback": "approved"},
            summary="Fallback approved.",
        )
        return SynthesisResult(
            round_num=synthesis_input.round_num,
            consensus_reached=True,
            agreement_count=1,
            total_agents=1,
            summary_for_shared_md=consensus.summary,
            consensus=consensus,
            source="static-fallback",
        )


@pytest.mark.asyncio
async def test_fallback_synthesis_agent_uses_fallback_on_primary_failure():
    agent = FallbackSynthesisAgent(
        primary=BrokenSynthesisAgent(),
        fallback=StaticFallbackAgent(),
    )

    result = await agent.synthesize(
        SynthesisInput(
            user_prompt="Design route bot",
            round_num=2,
            opinions={"claude": "anything"},
        )
    )

    assert result.consensus_reached is True
    assert result.source == "static-fallback"
    assert result.metadata["fallback_used"] is True
    assert result.diagnostics == [
        "primary synthesis failed: provider synthesis unavailable"
    ]
