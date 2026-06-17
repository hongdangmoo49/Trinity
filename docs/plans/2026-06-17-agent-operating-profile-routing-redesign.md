# Agent Operating Profile and Routing Redesign

작성일: 2026-06-17
작업 브랜치: `docs/agent-operating-profile-redesign`
상태: design draft

## 목적

현재 Trinity의 각 agent는 주로 `role_prompt`로만 정체성이 정의된다.

예:

| agent | 현재 역할 |
| :--- | :--- |
| Claude | 아키텍트 |
| Codex | 구현자 |
| Antigravity | 리뷰어 |

이 역할 구분은 처음 이해하기 쉽지만, 실제 workflow를 효율적으로 운영하기에는 정보가 부족하다.
에이전트가 어떤 작업을 잘하는지, 어떤 형식으로 답해야 하는지, 어떤 context를 받아야 하는지,
어떤 경우 리뷰/수리/설계를 맡아야 하는지가 코드 여러 곳에 흩어져 있기 때문이다.

이 문서는 Trinity의 agent 정의를 단순 역할에서 **운영 프로필**, **작업별 출력 계약**,
**프로필 기반 라우팅**, **역할별 context projection**, **품질 피드백 루프**로 확장하는 전체 설계를 정리한다.

## 관련 문서

- `docs/plans/2026-06-09-agent-resource-overlay-design.md`
- `docs/plans/2026-06-09-agent-targeted-chat-design.md`
- `docs/plans/2026-06-11-wp-non-owner-agent-reviews.md`
- `docs/plans/2026-06-17-selective-peer-review-policy-redesign.md`
- `docs/plans/2026-06-17-execution-status-review-sync-redesign.md`
- `docs/plans/2026-06-17-execution-page-uiux-redesign.md`

## 현재 상태

### AgentSpec

현재 `AgentSpec`은 provider 실행에 필요한 최소 정보와 역할 문구를 가진다.

주요 필드:

```text
name
provider
cli_command
model
role_prompt
role_file
workspace_mode
branch_template
context_budget
enabled
extra_args
resources.*
```

이 구조는 provider wrapper를 만들기에는 충분하지만, workflow orchestration 정책을 표현하기에는 부족하다.

### 기본 역할

기본 역할 문구는 `src/trinity/i18n.py`의 `ROLE_PROMPTS`에 있다.

현재 역할은 자연어 설명이다.

```text
Claude: Architect
Codex: Implementer
Antigravity: Reviewer
```

이 문구는 provider system prompt에 들어가지만, Trinity 내부의 작업 배정/리뷰/출력 파싱 정책과 직접 연결되어 있지 않다.

### 작업 분배

`TaskDistributor.DEFAULT_STRENGTHS`는 agent별 강점을 코드에 직접 갖고 있다.

```text
claude: architecture, design, code review, planning...
codex: implementation, coding, testing...
antigravity: testing, research, review...
```

문제:

- 사용자가 agent 역할을 바꿔도 분배 정책은 따라 바뀌지 않는다.
- provider가 1개 또는 2개만 활성화된 경우 강점 기반 fallback이 약하다.
- task kind가 명시적 타입이 아니라 keyword match에 가깝다.

### Blueprint decomposition

`BlueprintDecomposer.AGENT_FOCUS`도 별도 하드코딩이다.

```text
codex: implementation and integration
claude: architecture and planning
antigravity: validation and exploration
```

문제:

- `TaskDistributor.DEFAULT_STRENGTHS`와 정보가 중복된다.
- 동일한 agent 능력이 여러 파일에서 다른 기준으로 해석된다.
- 사용자 설정이나 품질 기록을 반영하기 어렵다.

### 리뷰 정책

선택형 peer review 정책 이후 기본 리뷰는 WP당 non-owner reviewer 1명으로 줄었다.
다만 reviewer priority는 아직 정책 코드에 직접 들어 있다.

```text
PRIMARY_REVIEWER_PRIORITY = antigravity, claude, codex
```

문제:

- 리뷰어 선택 기준이 agent profile과 분리되어 있다.
- high risk, 파일 영역, 최근 부하, 최근 품질을 반영하는 확장점이 약하다.
- 사용자가 Antigravity를 비활성화하거나 다른 역할로 바꿔도 priority 의미가 고정된다.

### 프롬프트와 출력 형식

현재 실행/리뷰 프롬프트에는 이미 기본 출력 형식이 있다.

실행:

```text
## Completed
## Files Changed
## Decisions Made
## Blockers
## Follow-up
## Subtasks
```

리뷰:

```text
REVIEW STATUS
SEVERITY
SUMMARY
FINDINGS
REQUIRED CHANGES
REVIEWED FILES
EXECUTION RISKS
ANTI PATTERNS
PERFORMANCE NOTES
FOLLOW UP
```

문제:

- 출력 형식이 prompt builder 내부 문자열로 고정되어 있다.
- agent별 또는 mode별 차이를 표현하기 어렵다.
- parser와 prompt contract가 한 곳에서 관리되지 않는다.
- 사용자 질문에 답하는 chat mode와 파일을 수정하는 execution mode가 같은 역할 프롬프트에 의존한다.

### Context projection

Trinity는 shared context, resource overlay, memory index를 가지고 있지만, agent 역할별로 context를 다르게 주는 정책은 아직 약하다.

예:

| mode | 필요한 context |
| :--- | :--- |
| architecture/plan | blueprint, 결정 기록, 의존성, 리스크 |
| execute | 현재 WP, expected files, acceptance criteria, 관련 결정 |
| review | diff/result, changed files, 테스트 결과, acceptance criteria |
| repair | review findings, required changes, 실패 로그 |

현재는 이 차이가 명확한 프로필 정책으로 표현되어 있지 않다.

## 문제 정의

현재 구조의 가장 큰 문제는 **agent 역할이 사람에게 보이는 설명으로만 존재하고, orchestration policy의 source of truth가 아니라는 점**이다.

그 결과 다음 문제가 생긴다.

1. 같은 능력 정보가 `i18n`, `TaskDistributor`, `BlueprintDecomposer`, `PeerReviewPlanner`에 흩어진다.
2. agent별 답변 형식을 안정적으로 제어하기 어렵다.
3. provider 수가 1개/2개/3개일 때 작업, 리뷰, self-check 정책을 일관되게 설명하기 어렵다.
4. 비용이 높은 provider와 빠른 provider를 다르게 쓰는 정책을 표현하기 어렵다.
5. 과거 성공률이나 리뷰 품질을 다음 라우팅에 반영할 수 없다.
6. UI는 agent의 "역할"만 보여줄 수 있고, 왜 이 agent가 이 WP를 맡았는지 설명하기 어렵다.

## 목표

1. `role_prompt`를 유지하면서 그 위에 `AgentProfile`을 도입한다.
2. agent 능력, 선호 작업, 회피 작업, 리뷰 focus, 비용/지연 특성을 config로 표현한다.
3. 작업 모드별 출력 계약을 중앙화한다.
4. TaskDistributor, BlueprintDecomposer, PeerReviewPlanner가 같은 profile source를 사용하게 한다.
5. provider 개수별 정책을 명확히 유지한다.
6. 역할별 context projection을 가능하게 한다.
7. 실행 결과와 리뷰 결과를 품질 지표로 축적해 후속 라우팅에 반영할 수 있게 한다.
8. 기존 config와 workflow session을 깨지 않도록 단계적으로 마이그레이션한다.

## 비목표

- provider CLI 자체의 native role/session 기능을 바꾸지 않는다.
- Claude/Codex/Antigravity의 실제 모델 성능을 이 문서에서 고정하지 않는다.
- 첫 구현에서 LLM 기반 동적 라우터를 만들지 않는다.
- 모든 prompt를 한 번에 갈아엎지 않는다.
- 사용자가 custom role_prompt를 작성한 기존 config를 덮어쓰지 않는다.
- 품질 지표를 provider 평가나 순위표처럼 사용자에게 과장 표시하지 않는다.

## 용어

| 용어 | 의미 |
| :--- | :--- |
| role prompt | provider에게 전달되는 자연어 역할 문구 |
| operating profile | Trinity 내부 라우팅/프롬프트/context 정책에 쓰이는 구조화된 agent 설명 |
| turn mode | chat, plan, execute, review, repair 같은 호출 목적 |
| output contract | 특정 turn mode에서 반드시 반환해야 하는 섹션/필드 형식 |
| task kind | implementation, architecture, testing, documentation 같은 작업 유형 |
| routing score | 후보 agent가 특정 작업에 적합한지 계산한 점수 |
| context projection | agent/mode에 맞춰 shared context 중 필요한 부분만 전달하는 것 |
| quality signal | 실행 성공률, 리뷰 결과, 재작업률 등 다음 라우팅에 사용할 관측값 |

## 설계 원칙

1. `role_prompt`는 provider-facing identity로 유지한다.
2. `AgentProfile`은 Trinity-facing orchestration contract다.
3. 기본값은 현재 동작과 최대한 동일해야 한다.
4. 하드코딩된 agent 강점은 profile default로 이동한다.
5. 출력 계약은 prompt builder와 parser가 같은 정의를 참조해야 한다.
6. provider가 1개뿐이어도 workflow가 과장된 품질 신호를 보여주면 안 된다.
7. routing은 첫 단계에서 결정론적이어야 한다.
8. 품질 지표는 advisory signal로 시작하고, 자동 차단 조건으로 바로 쓰지 않는다.
9. UI는 "누가 맡았는가"뿐 아니라 "왜 맡았는가"를 설명할 수 있어야 한다.
10. 구현은 작은 브랜치 단위로 순차 적용한다.

## Target Architecture

```text
TrinityConfig
  agents.<name>
    AgentSpec
    AgentProfile
      mission
      strengths
      preferred_task_kinds
      avoid_task_kinds
      review_focus
      turn_modes
      output_contracts
      routing
      context_profile

AgentProfileRegistry
  loads defaults
  merges user config
  resolves legacy role_prompt only configs

PromptComposer
  role prompt
  operating profile summary
  turn mode instructions
  task payload
  context projection
  output contract

RoutingPolicy
  task classification
  fit score
  load/cost/risk modifiers
  provider-count fallback

QualityLedger
  execution signals
  review signals
  repair signals
  aggregate advisory score
```

## AgentProfile 모델

### Python 모델 초안

```python
@dataclass
class AgentProfile:
    mission: str = ""
    summary: str = ""
    strengths: dict[str, float] = field(default_factory=dict)
    preferred_task_kinds: list[str] = field(default_factory=list)
    avoid_task_kinds: list[str] = field(default_factory=list)
    review_focus: list[str] = field(default_factory=list)
    supported_turn_modes: list[str] = field(default_factory=list)
    default_turn_mode: str = "chat"
    output_contracts: dict[str, str] = field(default_factory=dict)
    context_profile: str = "balanced"
    cost_tier: str = "medium"
    latency_tier: str = "medium"
    risk_tolerance: str = "medium"
    routing_priority: int = 100
```

### Task kind vocabulary

초기 task kind는 작고 명확하게 시작한다.

| kind | 의미 |
| :--- | :--- |
| `architecture` | 구조 설계, 경계 설정, 의사결정 |
| `planning` | 실행 전 분석, 순서화, 작업 분해 |
| `implementation` | 코드 작성, 기능 구현 |
| `large_implementation` | 범위가 크거나 파일 변경이 많은 구현 |
| `integration` | 모듈 연결, provider/CLI/API 연결 |
| `refactor` | 구조 개선, 중복 제거 |
| `testing` | 테스트 추가, 검증, 재현 |
| `review` | 변경 검토, 리스크 식별 |
| `documentation` | README, 계획 문서, 사용자 문서 |
| `research` | 대안 조사, 외부 의존성 탐색 |
| `repair` | 리뷰/실패 결과 기반 수정 |
| `release` | 버전, changelog, PR/merge 준비 |

### Turn mode vocabulary

| mode | 목적 | 파일 수정 |
| :--- | :--- | :--- |
| `chat` | 사용자 질문에 답변 | 없음 |
| `plan` | 설계/분석/작업 분해 | 없음 |
| `blueprint` | 실행 가능한 WP 그래프 작성 | 없음 |
| `execute` | WP 구현 | 있음 |
| `review` | WP peer review | 없음 |
| `final_review` | 전체 결과 검토 | 없음 |
| `repair` | 리뷰 결과 기반 최소 수정 | 있음 |
| `summarize` | 결과 요약/보고 | 없음 |

## 기본 프로필

### Claude 기본값

```toml
[agents.claude.profile]
mission = "아키텍처, 설계 검토, 고수준 의사결정"
summary = "복잡한 요구사항을 구조화하고 위험한 결정을 조기에 발견한다."
preferred_task_kinds = ["architecture", "planning", "review", "documentation"]
avoid_task_kinds = ["large_implementation"]
review_focus = ["architecture", "compatibility", "maintainability", "scope"]
supported_turn_modes = ["chat", "plan", "blueprint", "review", "final_review"]
context_profile = "architect"
cost_tier = "high"
latency_tier = "medium"
risk_tolerance = "high"
routing_priority = 20

[agents.claude.profile.strengths]
architecture = 0.95
planning = 0.90
review = 0.80
documentation = 0.75
implementation = 0.45
testing = 0.55
```

### Codex 기본값

```toml
[agents.codex.profile]
mission = "구현, 리팩터링, 테스트 자동화"
summary = "합의된 설계를 코드와 테스트로 빠르게 전환한다."
preferred_task_kinds = ["implementation", "integration", "refactor", "testing", "repair"]
avoid_task_kinds = ["architecture"]
review_focus = ["runtime_correctness", "test_coverage", "edge_cases"]
supported_turn_modes = ["chat", "plan", "execute", "review", "repair", "summarize"]
context_profile = "implementer"
cost_tier = "medium"
latency_tier = "fast"
risk_tolerance = "medium"
routing_priority = 10

[agents.codex.profile.strengths]
implementation = 0.95
integration = 0.85
refactor = 0.80
testing = 0.80
review = 0.65
architecture = 0.45
documentation = 0.55
```

### Antigravity 기본값

```toml
[agents.antigravity.profile]
mission = "검증, 대안 탐색, 품질 리스크 발견"
summary = "작업 결과의 빈틈과 edge case를 찾고 검증 방법을 제안한다."
preferred_task_kinds = ["review", "testing", "research", "documentation"]
avoid_task_kinds = ["large_implementation"]
review_focus = ["edge_cases", "regression", "performance", "anti_patterns"]
supported_turn_modes = ["chat", "plan", "review", "final_review", "summarize"]
context_profile = "reviewer"
cost_tier = "medium"
latency_tier = "medium"
risk_tolerance = "medium"
routing_priority = 30

[agents.antigravity.profile.strengths]
review = 0.95
testing = 0.85
research = 0.75
documentation = 0.65
implementation = 0.40
architecture = 0.55
```

## Config 구조

### Backward compatibility

기존 config는 계속 유효해야 한다.

```toml
[agents.codex]
provider = "codex"
cli_command = "codex"
role_prompt = "You are the Implementer..."
enabled = true
```

`profile`이 없으면 agent 이름과 provider를 기준으로 기본 profile을 합성한다.

### 새 config 예시

```toml
[agents.codex]
provider = "codex"
cli_command = "codex"
role_prompt = "당신은 구현자입니다..."
enabled = true

[agents.codex.profile]
mission = "Trinity repo 구현과 테스트 담당"
preferred_task_kinds = ["implementation", "testing", "repair"]
avoid_task_kinds = ["release"]
context_profile = "implementer"
cost_tier = "medium"
latency_tier = "fast"

[agents.codex.profile.strengths]
implementation = 1.0
testing = 0.9
documentation = 0.4

[agents.codex.profile.output_contracts]
execute = "execution_v1"
review = "review_v1"
repair = "repair_v1"
```

### 저장 정책

초기 구현에서는 `profile`을 사용자가 수정한 경우에만 config에 저장한다.
기본 profile까지 모두 저장하면 config가 지나치게 길어지고, 기본값 업데이트가 어려워진다.

권장 정책:

| 상황 | 저장 |
| :--- | :--- |
| 기본 profile 그대로 | 저장하지 않음 |
| wizard에서 사용자가 수정 | 수정 필드만 저장 |
| `trinity config`로 명시 수정 | 수정 필드만 저장 |
| export/debug | resolved profile 전체 표시 |

## Profile Resolution

`AgentProfileRegistry`를 추가한다.

역할:

1. agent name과 provider로 기본 profile을 찾는다.
2. config의 `[agents.<name>.profile]` override를 병합한다.
3. legacy custom `role_prompt`를 보존한다.
4. 지원하지 않는 strength key나 turn mode를 진단 warning으로 남긴다.
5. resolved profile을 orchestration component에 제공한다.

우선순위:

```text
hardcoded defaults
  < localized defaults
  < provider-specific defaults
  < config profile override
  < invocation override
```

초기 구현에서는 hardcoded defaults와 config override만 사용해도 충분하다.

## Prompt Composer

현재 prompt 조립은 provider invoker, execution protocol, review protocol, deliberation protocol에 흩어져 있다.
첫 구현에서 모든 프롬프트를 통합하지 않고, 작은 `PromptComposer` 또는 `TurnPromptContract` 유틸을 추가해 점진 적용한다.

### Prompt layer

권장 layer:

```text
[System Role]
provider-facing role_prompt

[Operating Profile]
mission
strengths relevant to current mode
review_focus or execution_focus
constraints

[Turn Mode]
mode-specific instructions

[Context Projection]
mode/agent에 필요한 context

[Task Payload]
WP, review package, user prompt 등 실제 입력

[Output Contract]
반드시 지킬 응답 형식
```

### 적용 순서

1. 기존 role prompt 전달 방식은 그대로 둔다.
2. execution/review prompt 끝의 출력 형식을 `OutputContract`에서 렌더링한다.
3. deliberation structured contract도 같은 registry로 옮긴다.
4. provider invoker의 `_render_prompt`는 최종 문자열만 받도록 유지한다.

## Output Contracts

### Contract 모델 초안

```python
@dataclass(frozen=True)
class OutputContract:
    id: str
    mode: str
    required_sections: tuple[str, ...]
    optional_sections: tuple[str, ...] = ()
    status_field: str = ""
    allowed_statuses: tuple[str, ...] = ()
    parser: str = ""
    localized_instructions: dict[str, str] = field(default_factory=dict)
```

### execution_v1

```text
## Completed
## Files Changed
## Decisions Made
## Blockers
## Follow-up
## Subtasks
```

추가 권장:

```text
## Tests
## Verification
```

단, parser 호환을 위해 추가 섹션은 optional로 시작한다.

### review_v1

```text
REVIEW STATUS: APPROVED | CHANGES_REQUESTED | BLOCKED
SEVERITY: LOW | MEDIUM | HIGH | CRITICAL

SUMMARY:
FINDINGS:
REQUIRED CHANGES:
REVIEWED FILES:
EXECUTION RISKS:
ANTI PATTERNS:
PERFORMANCE NOTES:
FOLLOW UP:
```

### repair_v1

```text
## Repair Summary
## Addressed Findings
## Files Changed
## Tests
## Remaining Risk
## Follow-up
```

### plan_v1

```text
## Goal
## Current State
## Proposed Design
## Work Packages
## Risks
## Acceptance Criteria
## Open Questions
```

### chat_v1

Chat mode는 너무 강한 형식을 요구하지 않는다.

권장:

```text
- 답변은 사용자의 언어를 따른다.
- 파일을 수정하지 않는다.
- 구현이 필요하면 명시적으로 다음 작업을 제안한다.
- 불확실한 사실은 확인 필요 여부를 표시한다.
```

## Routing Policy

### Task classification

라우팅 전에 task kind를 분류한다.

입력:

- user prompt
- blueprint section
- work package title/objective/scope
- expected files
- risk
- requires_execution
- review depth

출력:

```python
@dataclass(frozen=True)
class ClassifiedTask:
    kind: str
    turn_mode: str
    risk: str
    expected_files: tuple[str, ...]
    requires_write: bool
    confidence: float
```

첫 구현은 deterministic keyword 기반으로 충분하다.
이후 synthesis model이 work package에 `kind`를 직접 넣게 확장할 수 있다.

### Score 계산

초기 score:

```text
score =
  profile.strengths[kind] * 100
  + preferred_task_bonus
  - avoid_task_penalty
  - unsupported_mode_penalty
  - high_risk_mismatch_penalty
  - current_load_penalty
  - recent_failure_penalty
  - cost_penalty
  + latency_bonus
  - routing_priority_tiebreak
```

초기 구현에서 꼭 필요한 항목:

| 항목 | 필요성 |
| :--- | :--- |
| strength score | 기존 하드코딩 대체 |
| supported turn mode | 실행 불가 agent 배제 |
| avoid task penalty | 잘못된 배정 방지 |
| provider count fallback | 1/2 provider UX 보존 |
| deterministic tiebreak | 테스트 안정성 |

후속 구현 항목:

| 항목 | 이유 |
| :--- | :--- |
| current load | 병렬 실행 시 특정 agent 편중 완화 |
| quality score | 과거 성과 반영 |
| cost/latency score | 저비용/고속 provider 선호 가능 |
| file ownership score | expected files와 agent 경험 연결 |

### Provider 수별 정책

프로필 기반 라우팅도 provider 개수별 기본 UX를 지켜야 한다.

| 활성 provider 수 | 실행 | 리뷰 |
| :--- | :--- | :--- |
| 1 | 유일한 provider가 실행 | peer review 없음, 필요 시 self-check |
| 2 | profile score로 실행자 결정 | non-owner 1명 리뷰 |
| 3+ | profile score + load로 실행자 결정 | primary reviewer 1명, 조건부 escalation |

중요:

- provider 1개에서 self-check를 하더라도 peer approved처럼 표시하지 않는다.
- provider 2개에서 reviewer 선택은 사실상 고정이므로 UI에 "only available peer" reason을 남긴다.
- provider 3개 이상에서는 reviewer 선택 reason을 event/session에 기록한다.

## BlueprintDecomposer 변경

현재 `AGENT_FOCUS`를 profile 기반으로 이동한다.

변경 전:

```text
seed kind + hardcoded AGENT_FOCUS + provider priority
```

변경 후:

```text
seed -> ClassifiedTask -> RoutingPolicy.select_owner()
```

초기 migration:

1. `AGENT_FOCUS` 값과 동일한 기본 profile을 만든다.
2. `_agent_fit_score()` 내부에서 profile registry를 사용한다.
3. 기존 test expectation이 깨지지 않도록 default score를 현재와 맞춘다.

## TaskDistributor 변경

현재 `DEFAULT_STRENGTHS`를 profile registry로 대체한다.

변경 전:

```text
agent_name -> DEFAULT_STRENGTHS -> matched keywords
```

변경 후:

```text
agent_name -> resolved profile -> strengths/preferred_task_kinds
```

Design-only, execution, plan intent 분류는 유지하되, task description에는 다음을 추가한다.

```text
Agent mission
Selected focus
Routing reason
Expected output mode
```

## PeerReviewPlanner 변경

리뷰어 선택은 `review_focus`, `strengths.review`, `current_load`, `recent_quality`를 볼 수 있어야 한다.

초기 변경:

```text
non-owner candidates
  -> supported_turn_modes includes review
  -> review strength score
  -> default priority tiebreak
```

기존 priority와 호환:

```text
Antigravity review strength highest
Claude second
Codex third
```

그래서 기본 결과는 현재 정책과 거의 동일하다.

## Context Projection

### ContextProfile

```python
@dataclass(frozen=True)
class ContextProfile:
    id: str
    include_sections: tuple[str, ...]
    include_recent_events: bool = True
    include_execution_results: bool = False
    include_review_results: bool = False
    include_changed_files: bool = False
    max_chars: int = 0
```

### 기본 context profile

| profile | 대상 | 포함 |
| :--- | :--- | :--- |
| `architect` | Claude plan/blueprint | goal, agreed conclusion, decisions, risks, package graph |
| `implementer` | Codex execute/repair | current WP, expected files, acceptance criteria, relevant decisions, blockers |
| `reviewer` | Antigravity review | execution summary, changed files, acceptance criteria, review criteria, risk |
| `balanced` | custom/default | 현재 기본 context와 유사 |

### 적용 지점

초기에는 prompt에 들어가는 context 문자열을 줄이는 방향으로만 적용한다.
provider resource overlay나 memory index는 그대로 유지한다.

후속 단계에서 `ResourceProjector`와 연결해 agent/mode별 resource activation까지 확장할 수 있다.

## Quality Ledger

품질 지표는 즉시 자동 라우팅을 바꾸기보다는, advisory signal로 저장한다.

### 저장할 signal

| signal | source |
| :--- | :--- |
| execution success/failure | `ExecutionResult.status` |
| blockers count | `ExecutionResult.blockers` |
| files changed count | `ExecutionResult.files_changed` |
| review status | `ReviewResult.status` |
| required changes count | `ReviewResult.required_changes` |
| escalation count | `ReviewPackage.depth` |
| repair required | review result + follow-up workflow |
| elapsed time | provider invocation metadata |
| token/context usage | existing context usage metadata |

### Aggregation

초기 score는 단순 이동 평균으로 충분하다.

```text
agent_quality_score =
  success_rate
  - required_change_rate
  - blocker_rate
  - retry_rate
```

이 값은 다음 두 용도로 먼저 사용한다.

1. UI/diagnostics에 routing reason으로 표시
2. 동점일 때 tie-break signal로 사용

자동으로 특정 agent를 배제하는 정책은 별도 사용자 설정이 있을 때만 활성화한다.

## UI/UX 반영

실행 페이지와 설정 화면은 단순 역할보다 더 유용한 정보를 보여줘야 한다.

### Settings

Agent card:

```text
Codex
Role: Implementer
Mission: 구현, 리팩터링, 테스트 자동화
Strengths: implementation 0.95, testing 0.80
Modes: execute, review, repair
Cost: medium · Latency: fast
```

### Execution Page

WP row detail:

```text
Owner: Codex
Reason: highest implementation fit, fast latency, available
Review: Antigravity
Review reason: strongest review focus, non-owner
```

### Provider Inspector

Provider inspector에는 resolved profile과 active output contract를 보여준다.

```text
Active mode: execute
Output contract: execution_v1
Context profile: implementer
Routing score: 91
```

## Events and Persistence

라우팅 결과와 이유는 event/session에 남긴다.

### 새 event payload 후보

```json
{
  "event": "WORK_PACKAGE_ROUTED",
  "package_id": "WP-001",
  "owner_agent": "codex",
  "task_kind": "implementation",
  "turn_mode": "execute",
  "routing_score": 91.5,
  "routing_reason": "implementation strength + available + fast latency",
  "profile_revision": "default-v1"
}
```

Review package event:

```json
{
  "event": "REVIEW_PACKAGE_PLANNED",
  "review_package_id": "RP-WP-001-antigravity",
  "reviewer_agent": "antigravity",
  "depth": "single_peer",
  "routing_reason": "highest review strength among non-owner agents"
}
```

## Migration

### Existing config

기존 config는 그대로 읽힌다.

```text
profile missing -> default profile resolved at runtime
```

### Existing sessions

기존 workflow session에는 profile 관련 필드가 없을 수 있다.
resume 시 다음처럼 처리한다.

```text
missing routing_reason -> "(legacy assignment)"
missing profile_revision -> "legacy"
missing output_contract -> infer by prompt/parser version
```

### Custom role_prompt

custom `role_prompt`는 절대 덮어쓰지 않는다.
다만 profile이 없으면 agent name/provider 기반 기본 profile을 사용한다.

향후 wizard에서 다음 선택지를 제공할 수 있다.

```text
1. 역할 문구만 수정
2. 운영 프로필도 함께 수정
3. 기본 운영 프로필로 되돌리기
```

## 구현 순서

작업은 순서대로 진행한다.

### 1단계: AgentProfile 모델과 기본 registry

목표:

- `AgentProfile` dataclass 추가
- 기본 profile 정의
- config load 시 profile override 읽기
- 기존 config 호환 유지

영향 파일:

- `src/trinity/models.py`
- `src/trinity/config.py`
- `src/trinity/i18n.py`
- `tests/test_config*.py`
- `tests/test_setup*.py`

완료 기준:

- profile 없는 config가 기존처럼 로드된다.
- 기본 3 agent의 resolved profile이 생성된다.
- profile override가 저장/로드된다.

권장 브랜치:

```text
feature/agent-profile-model
```

### 2단계: OutputContract registry

목표:

- execution/review/plan/chat contract를 중앙 정의로 이동
- 기존 parser와 호환
- prompt builder는 contract renderer를 사용

영향 파일:

- `src/trinity/workflow/execution.py`
- `src/trinity/workflow/review_execution.py`
- `src/trinity/deliberation/protocol.py`
- 신규 `src/trinity/prompts/contracts.py`

완료 기준:

- 기존 execution/review parser 테스트가 통과한다.
- prompt 내용은 의미상 기존과 동일하다.
- contract id가 result metadata 또는 event에 남는다.

권장 브랜치:

```text
feature/agent-output-contracts
```

### 3단계: 프로필 기반 작업 라우팅

목표:

- `TaskDistributor.DEFAULT_STRENGTHS` 제거 또는 compatibility wrapper화
- `BlueprintDecomposer.AGENT_FOCUS`를 profile registry로 대체
- routing reason 저장

영향 파일:

- `src/trinity/deliberation/distributor.py`
- `src/trinity/workflow/decomposer.py`
- 신규 `src/trinity/routing/profile_router.py`
- `src/trinity/workflow/models.py`

완료 기준:

- 기본 3 provider에서 기존과 유사한 WP owner가 나온다.
- custom profile strength가 owner 배정에 반영된다.
- 라우팅 이유가 WP repair notes 또는 event에 남는다.

권장 브랜치:

```text
feature/profile-based-routing
```

### 4단계: 프로필 기반 리뷰어 선택

목표:

- `PRIMARY_REVIEWER_PRIORITY`를 profile score 기반으로 전환
- provider 1/2/3개 정책 유지
- escalation reviewer도 profile 기반 선택

영향 파일:

- `src/trinity/workflow/review.py`
- `src/trinity/workflow/review_execution.py`
- `src/trinity/textual_app/snapshot.py`
- `src/trinity/textual_app/screens/execution_matrix.py`

완료 기준:

- provider 1개: peer review skipped 유지
- provider 2개: non-owner 1명 리뷰 유지
- provider 3개: 기본적으로 review strength가 높은 non-owner 1명 선택
- review package에 reason이 남는다.

권장 브랜치:

```text
feature/profile-based-review-routing
```

### 5단계: ContextProfile projection

목표:

- agent/mode별 context profile 적용
- 실행/리뷰 prompt에 필요한 context만 전달
- 비용 증가 없이 prompt relevance 향상

영향 파일:

- `src/trinity/context/shared.py`
- `src/trinity/context/memory.py`
- `src/trinity/resources/projector.py`
- `src/trinity/workflow/execution.py`
- `src/trinity/workflow/review_execution.py`

완료 기준:

- execute mode는 WP 관련 context를 우선 전달한다.
- review mode는 execution result와 changed files를 우선 전달한다.
- context projection metadata가 event/debug에 남는다.

권장 브랜치:

```text
feature/agent-context-profiles
```

### 6단계: QualityLedger와 routing feedback

목표:

- execution/review/repair signal 저장
- agent별 advisory quality score 계산
- 라우팅 동점 처리에만 반영

영향 파일:

- `src/trinity/workflow/ledger.py`
- `src/trinity/workflow/execution.py`
- `src/trinity/workflow/review_execution.py`
- `src/trinity/textual_app/snapshot.py`
- 신규 `src/trinity/routing/quality.py`

완료 기준:

- agent별 success/review/change signal이 저장된다.
- score가 session resume 후에도 복원된다.
- score가 없는 기존 session은 안전하게 동작한다.

권장 브랜치:

```text
feature/agent-quality-routing-signals
```

### 7단계: UI/UX 노출

목표:

- settings/provider inspector/execution detail에서 resolved profile 표시
- routing reason 표시
- output contract/context profile 표시

영향 파일:

- `src/trinity/textual_app/screens/settings.py`
- `src/trinity/textual_app/widgets/provider_inspector.py`
- `src/trinity/textual_app/screens/execution_matrix.py`
- `src/trinity/textual_app/snapshot.py`

완료 기준:

- 사용자가 왜 이 agent가 선택되었는지 볼 수 있다.
- role, mission, modes, strengths가 간결하게 표시된다.
- 좁은 터미널에서도 핵심 정보가 깨지지 않는다.

권장 브랜치:

```text
feature/agent-profile-ui
```

## 테스트 전략

### Unit tests

- profile default resolution
- config profile override parse/save
- invalid strength/mode validation
- routing score deterministic ordering
- provider count fallback
- output contract rendering
- execution/review parser compatibility
- quality score aggregation

### Integration tests

- 1 provider workflow: execution + skipped peer review
- 2 provider workflow: execution + one peer review
- 3 provider workflow: profile-selected owner + profile-selected reviewer
- custom profile changes owner selection
- resume legacy session without profile fields

### UI snapshot tests

- settings profile summary
- execution matrix routing reason
- review skipped vs approved labels
- provider inspector active mode/contract

## Acceptance Criteria

전체 설계가 구현되면 다음이 가능해야 한다.

1. 기존 `.trinity/trinity.config`가 수정 없이 동작한다.
2. 각 agent는 role뿐 아니라 mission, strengths, modes, cost/latency tier를 가진다.
3. WP owner와 reviewer 선택이 같은 profile source를 사용한다.
4. 실행/리뷰/수리/계획 응답 형식이 중앙 contract로 관리된다.
5. provider가 1개 또는 2개일 때도 리뷰 UX가 과장되지 않는다.
6. 실행 페이지에서 owner/reviewer 선택 이유를 확인할 수 있다.
7. context projection으로 provider 호출 입력이 더 목적 지향적으로 줄어든다.
8. 품질 지표가 저장되지만 초기에는 보수적으로만 라우팅에 반영된다.

## 리스크와 완화

| 리스크 | 완화 |
| :--- | :--- |
| config가 복잡해짐 | 기본 profile은 저장하지 않고 override만 저장 |
| 기존 테스트 대량 변경 | 기본 profile 값을 현재 하드코딩과 맞춤 |
| prompt 변경으로 parser 실패 | contract 도입 후 parser compatibility test 먼저 고정 |
| score 기반 라우팅이 예측 불가 | 초기에는 deterministic score와 명시적 tie-break 사용 |
| 품질 지표가 잘못된 편견을 만듦 | advisory/tie-break 용도로만 시작 |
| UI 정보 과다 | settings/inspector/detail에 분산하고 row에는 reason summary만 표시 |

## 구현 메모

우선순위는 다음이다.

1. 모델과 config 호환성
2. 출력 계약 중앙화
3. 작업 라우팅
4. 리뷰 라우팅
5. context projection
6. 품질 feedback
7. UI 노출

가장 먼저 구현해야 할 것은 `AgentProfile` 자체다.
이 모델이 생기면 나머지 작업은 기존 하드코딩을 하나씩 profile lookup으로 바꾸는 식으로 진행할 수 있다.

## 미결정 사항

1. `AgentProfile`을 `AgentSpec` 안에 직접 넣을지, 별도 registry result로만 둘지 결정해야 한다.
2. profile override 저장 시 부분 저장과 전체 저장 중 어떤 UX를 기본으로 할지 정해야 한다.
3. 품질 지표 저장 위치를 `workflow/ledger.py`에 둘지, 별도 `routing/quality.py`에 둘지 정해야 한다.
4. output contract localization을 `i18n.py`에 둘지, prompt contract registry에 둘지 정해야 한다.
5. 사용자에게 strength score를 숫자로 보여줄지, high/medium/low label로 변환할지 정해야 한다.
