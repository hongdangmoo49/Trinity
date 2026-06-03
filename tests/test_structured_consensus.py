"""Tests for structured deliberation synthesis."""

from trinity.workflow.structured import StructuredConsensusSynthesizer, VoteType


BLUEPRINT_TEXT = """\
BLUEPRINT:
Title: L2 Bridge Path Bot
Summary: Finds reliable bridge routes across layer 2 networks.

Architecture:
- Quote Collector: collects bridge quotes from providers
- Route Scorer: ranks routes by fee, latency, and reliability

Data Flow:
- User request -> Quote Collector -> Route Scorer -> ranked routes

External Dependencies:
- Hop API
- Across API

Risks:
- stale quotes

Acceptance Criteria:
- ranks routes by fee and latency

VOTE: APPROVE
"""


def test_single_agent_blueprint_reaches_consensus():
    synthesizer = StructuredConsensusSynthesizer()

    result = synthesizer.evaluate({"claude": BLUEPRINT_TEXT})

    assert result.reached is True
    assert result.vote_count[VoteType.APPROVE] == 1
    assert result.final_blueprint is not None
    assert result.final_blueprint.title == "L2 Bridge Path Bot"
    assert result.approval_count == 1


def test_approve_with_changes_counts_toward_threshold():
    synthesizer = StructuredConsensusSynthesizer(required_fraction=0.6)

    result = synthesizer.evaluate(
        {
            "claude": BLUEPRINT_TEXT,
            "codex": "VOTE: APPROVE_WITH_CHANGES\nUse adapter interfaces.",
            "gemini": "VOTE: REJECT\nBlocker: provider risk matrix missing.",
        }
    )

    assert result.reached is True
    assert result.approval_count == 2
    assert result.vote_count[VoteType.APPROVE_WITH_CHANGES] == 1


def test_blocked_by_question_extracts_open_question():
    synthesizer = StructuredConsensusSynthesizer()
    text = """\
VOTE: BLOCKED_BY_QUESTION

OPEN QUESTIONS:
- Question: Optimize routes for cost, latency, or mixed score?
  Options: cost | latency | mixed
  Recommended: mixed
  Rationale: Bridge UX depends on fee, speed, and failure rate.
"""

    result = synthesizer.evaluate({"gemini": text})

    assert result.reached is False
    assert result.vote_count[VoteType.BLOCKED_BY_QUESTION] == 1
    assert len(result.open_questions) == 1
    question = result.open_questions[0]
    assert question.question == "Optimize routes for cost, latency, or mixed score?"
    assert question.options == ["cost", "latency", "mixed"]
    assert question.recommended_option == "mixed"
    assert question.raised_by == ["gemini"]


def test_reject_extracts_blocker():
    synthesizer = StructuredConsensusSynthesizer()

    result = synthesizer.evaluate(
        {"codex": "VOTE: REJECT\nBlocker: no execution boundary is defined."}
    )

    assert result.reached is False
    assert result.vote_count[VoteType.REJECT] == 1
    assert result.blockers == ["Blocker: no execution boundary is defined."]
