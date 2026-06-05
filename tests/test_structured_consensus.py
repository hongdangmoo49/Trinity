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
            "antigravity": "VOTE: REJECT\nBlocker: provider risk matrix missing.",
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

    result = synthesizer.evaluate({"antigravity": text})

    assert result.reached is False
    assert result.vote_count[VoteType.BLOCKED_BY_QUESTION] == 1
    assert len(result.open_questions) == 1
    question = result.open_questions[0]
    assert question.question == "Optimize routes for cost, latency, or mixed score?"
    assert question.options == ["cost", "latency", "mixed"]
    assert question.recommended_option == "mixed"
    assert question.raised_by == ["antigravity"]


def test_extracts_korean_question_fields_and_recommendation():
    synthesizer = StructuredConsensusSynthesizer()
    text = """\
VOTE: BLOCKED_BY_QUESTION

OPEN QUESTIONS:
# 1
질문: 브릿지 API 소스?
옵션: LI.FI, Socket, 자체 구축
추천: LI.FI
이유: 현재 API 커버리지와 서버비 부담이 가장 낮음.

# 2
질문: 언어/프레임워크?
옵션: TypeScript | Python | Rust
추천: TypeScript
근거: Web3 SDK 생태계 호환성이 높음.
"""

    result = synthesizer.evaluate({"claude": text})

    assert result.reached is False
    assert len(result.open_questions) == 2
    first, second = result.open_questions
    assert first.question == "브릿지 API 소스?"
    assert first.options == ["LI.FI", "Socket", "자체 구축"]
    assert first.recommended_option == "LI.FI"
    assert first.rationale == "현재 API 커버리지와 서버비 부담이 가장 낮음."
    assert second.question == "언어/프레임워크?"
    assert second.options == ["TypeScript", "Python", "Rust"]
    assert second.recommended_option == "TypeScript"
    assert second.rationale == "Web3 SDK 생태계 호환성이 높음."


def test_extracts_numbered_options_after_empty_options_label():
    synthesizer = StructuredConsensusSynthesizer()
    text = """\
VOTE: BLOCKED_BY_QUESTION

OPEN QUESTIONS:
- Question: MVP scope?
  Options:
  1. L2 only
  2. L2 plus Ethereum mainnet
  3. Include all L1s
  Recommended: L2 plus Ethereum mainnet
  Rationale: Most practical bridge paths use Ethereum as a fallback.
"""

    result = synthesizer.evaluate({"antigravity": text})

    assert len(result.open_questions) == 1
    question = result.open_questions[0]
    assert question.question == "MVP scope?"
    assert question.options == [
        "L2 only",
        "L2 plus Ethereum mainnet",
        "Include all L1s",
    ]
    assert question.recommended_option == "L2 plus Ethereum mainnet"


def test_reject_extracts_blocker():
    synthesizer = StructuredConsensusSynthesizer()

    result = synthesizer.evaluate(
        {"codex": "VOTE: REJECT\nBlocker: no execution boundary is defined."}
    )

    assert result.reached is False
    assert result.vote_count[VoteType.REJECT] == 1
    assert result.blockers == ["Blocker: no execution boundary is defined."]
