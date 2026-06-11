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


def test_extracts_korean_section_headings_with_modifiers():
    synthesizer = StructuredConsensusSynthesizer()
    text = """\
## 수정된 제안: 픽셀 탄막 슈팅 — 설계 확정

### 요약
싱글 로그라이트 탄막 서바이벌.

### 확정 아키텍처
- GameLoop: 런 상태와 난이도 곡선을 관리한다.

### 데이터 흐름
- 게임 시작 -> 캐릭터 선택 -> 30분 타이머 시작

### 외부 의존성 (최종)
- Godot 4.4+
- GodotSteam

### 리스크 (업데이트)
- 대량 적과 탄환 처리 성능 저하

### 수용 기준 (확정)
- 1920x1080에서 6배 정수 배율
- 적 200 + 총알 1000 동시 처리

VOTE: APPROVE
"""

    result = synthesizer.evaluate({"claude": text})

    assert result.reached is True
    assert result.final_blueprint is not None
    blueprint = result.final_blueprint
    assert [component.name for component in blueprint.architecture] == ["GameLoop"]
    assert blueprint.data_flow == ["게임 시작 -> 캐릭터 선택 -> 30분 타이머 시작"]
    assert blueprint.external_dependencies == ["Godot 4.4+", "GodotSteam"]
    assert [risk.description for risk in blueprint.risks] == [
        "대량 적과 탄환 처리 성능 저하"
    ]
    assert blueprint.acceptance_criteria == [
        "1920x1080에서 6배 정수 배율",
        "적 200 + 총알 1000 동시 처리",
    ]


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


def test_extracts_inline_vs_options_from_numbered_questions():
    synthesizer = StructuredConsensusSynthesizer()
    text = """\
VOTE: BLOCKED_BY_QUESTION

OPEN QUESTIONS:
- 1. **엔진 선택** - Godot vs Unity vs 자체 엔진?
- 2. **과금 모델** - F2P+광고 vs 유료 vs 하이브리드?
"""

    result = synthesizer.evaluate({"claude": text})

    assert result.reached is False
    assert len(result.open_questions) == 2
    first, second = result.open_questions
    assert first.question == "엔진 선택?"
    assert first.options == ["Godot", "Unity", "자체 엔진"]
    assert second.question == "과금 모델?"
    assert second.options == ["F2P+광고", "유료", "하이브리드"]


def test_reject_extracts_blocker():
    synthesizer = StructuredConsensusSynthesizer()

    result = synthesizer.evaluate(
        {"codex": "VOTE: REJECT\nBlocker: no execution boundary is defined."}
    )

    assert result.reached is False
    assert result.vote_count[VoteType.REJECT] == 1
    assert result.blockers == ["Blocker: no execution boundary is defined."]
