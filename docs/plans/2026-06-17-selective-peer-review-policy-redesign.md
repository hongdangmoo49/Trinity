# Selective Peer Review Policy Redesign

작성일: 2026-06-17
대상 branch/worktree: `docs/selective-review-policy` / `/home/user/workspace/Trinity-worktrees/review-policy`

## 목적

현재 Trinity는 각 WP가 끝난 뒤 작업 agent가 아닌 모든 활성 agent에게 리뷰를 맡기는 정책을 갖고 있다.
세 provider가 모두 켜져 있으면 WP 1개당 리뷰가 2개 발생한다.

사용자 목표는 다음과 같다.

- 실행 페이지의 기본 목표는 여러 agent가 WP를 병렬 실행하는 것이다.
- WP 완료 후 리뷰는 필요하지만, non-owner reviewer 둘 다 항상 리뷰할 필요는 없다.
- 사용자가 provider를 1개 또는 2개만 설정한 경우에도 UI/UX가 자연스러워야 한다.

## 현재 동작

### 리뷰 계획

`PeerReviewPlanner._reviewers_for()`는 활성 agent가 2개 이상이면 target agent를 제외한
모든 agent를 reviewer로 반환한다.

예:

| active agents | target | planned reviewers |
| :--- | :--- | :--- |
| Claude, Codex, Antigravity | Codex | Claude, Antigravity |
| Claude, Codex | Codex | Claude |
| Codex | Codex | Codex self-review |

현재 테스트 `test_peer_review_planner_assigns_all_non_owner_reviewers_per_work_package`도 이 계약을
명시한다.

### 리뷰 실행

`ReviewExecutionProtocol.review_work_packages()`는 review package 목록을 순회하며 실행한다.
현재 구조에서는 WP별 리뷰 2개가 생기면 provider 호출도 2번 발생하고, 기본 실행은 순차적이다.

## 문제

### 비용

3-provider 상태에서 WP가 N개면 work-package review 호출은 최대 `2N`개다.

예:

| WP 수 | 현재 리뷰 호출 수 |
| :--- | :--- |
| 3 | 6 |
| 6 | 12 |
| 10 | 20 |

각 리뷰는 provider CLI 호출이므로 시간, token, provider quota, local CPU/process 비용이 모두 증가한다.
실행 자체가 병렬이어도 리뷰가 과하게 많으면 전체 workflow 체감 속도가 느려진다.

### UX

- `Review` 컬럼이 `codex, antigravity`처럼 두 reviewer를 보여주면 어떤 리뷰가 필수인지 모호하다.
- 하나는 approved이고 하나는 changes requested일 때 사용자에게 어떤 결정을 요구하는지 불명확하다.
- provider가 1개뿐인 경우 self-review는 peer review가 아니므로 “검토 완료”처럼 보이면 신뢰를 과장한다.
- provider가 2개뿐인 경우 reviewer 선택 여지가 없는데도 3-provider UI와 같은 표현을 쓰면 헷갈린다.

## 새 정책 제안

### 기본 원칙

1. WP당 기본 reviewer는 1명이다.
2. 두 번째 reviewer는 조건부 escalation에서만 사용한다.
3. provider가 1개뿐이면 peer review를 강제로 꾸미지 않는다.
4. provider가 2개뿐이면 non-owner 한 명만 리뷰한다.
5. provider가 3개 이상이면 policy가 가장 적합한 reviewer 1명을 고른다.
6. final review는 work-package review와 별도이며, 기본 1명 + fallback만 유지한다.

## Review Depth

새 정책은 review depth를 명시한다.

| depth | 의미 | provider 호출 |
| :--- | :--- | :--- |
| `none` | 리뷰 생략 | 0 |
| `self_check` | peer reviewer 없음. owner가 자체 점검 | 0 또는 1 |
| `single_peer` | non-owner reviewer 1명 | 1 |
| `escalated_peer` | 1차 reviewer + 조건부 2차 reviewer | 1 또는 2 |

기본값은 `single_peer`다.

## Provider 수별 동작

### 활성 provider 1개

예: Codex만 enabled.

권장 동작:

- WP 실행은 Codex가 수행한다.
- peer review는 `skipped_no_peer`로 기록한다.
- high-risk WP 또는 사용자 설정이 있으면 `self_check`를 실행할 수 있다.
- UI는 “peer reviewer 없음”을 명확히 표시한다.

UI 표시:

```text
Review: skipped
Reason: only Codex is active
Action: enable another provider for peer review
```

절대 피해야 할 표현:

```text
Review: approved
```

peer review가 없는데 approved처럼 보이면 사용자가 품질 검증을 과신한다.

### 활성 provider 2개

예: Claude + Codex.

권장 동작:

- target agent를 제외한 나머지 1명이 reviewer다.
- reviewer 선택 여지가 없으므로 `single_peer`로 표시한다.

UI 표시:

```text
Review: Claude queued
Review: Claude reviewing
Review: approved by Claude
```

### 활성 provider 3개

예: Claude + Codex + Antigravity.

권장 동작:

- non-owner 후보 중 1명을 primary reviewer로 선택한다.
- 두 번째 reviewer는 아래 조건에서만 추가한다.
  - WP risk가 `high`
  - 1차 review가 `changes_requested`, `blocked`, `failed`
  - touched files가 보안/인증/데이터 마이그레이션 등 위험 영역
  - 사용자가 `/review --depth=two` 또는 설정으로 명시

UI 표시:

```text
Review: Antigravity reviewing
Review: changes by Antigravity
Action: request second review
```

## Reviewer 선택 기준

기본 reviewer scoring:

| 기준 | 설명 |
| :--- | :--- |
| role fit | 검토자 역할의 Antigravity 선호 |
| target diversity | target agent와 다른 provider |
| risk fit | high risk면 설계/검토 성향 agent 우선 |
| current load | 이미 실행/리뷰 중인 agent는 감점 |
| recent reviewer rotation | 같은 reviewer 편중 방지 |
| availability | disabled/unavailable provider 제외 |

초기 구현은 단순 deterministic policy로 시작한다.

```text
if active_count == 1:
    return skipped_no_peer or self_check
if active_count == 2:
    return only non-owner
if active_count >= 3:
    candidates = non-owner active agents
    prefer Antigravity if target != Antigravity
    else prefer Claude
    else prefer Codex
```

추후에는 work package metadata로 더 정교화한다.

## Data Model 변경

### ReviewPackage

추가 후보:

```text
depth: none | self_check | single_peer | escalated_peer
required: bool
reason: str
escalation_parent_id: str
skipped_reason: str
```

### ReviewResult

추가 후보:

```text
skipped: bool
skipped_reason: str
confidence: low | medium | high
```

단, schema churn을 줄이기 위해 첫 구현은 `ReviewPackage.scope`/metadata dict 확장 또는 event payload부터 시작할 수 있다.

## UI/UX 요구사항

### Execution Page

Review 컬럼은 reviewer 수를 명확히 보여준다.

| 상황 | 표시 |
| :--- | :--- |
| provider 1개 | `SKIP` 또는 `self-check` |
| provider 2개 | `Claude WAIT/RUN/DONE` |
| provider 3개 기본 | `Antigravity WAIT/RUN/DONE` |
| 2차 리뷰 필요 | `needs 2nd` |
| 2차 리뷰 진행 | `Claude 2nd RUN` |

WP detail modal에는 다음 섹션을 둔다.

```text
Review Plan
- required reviewer
- skipped reason
- escalation reason
- reviewer count

Review Results
- primary result
- secondary result, if any
```

### Settings

추후 설정:

```text
review_depth = auto | none | self-check | one | two
review_escalation = risk-only | changes-only | risk-or-changes | never
```

기본:

```text
review_depth = auto
review_escalation = risk-or-changes
```

## 실행 비용 비교

세 provider, WP 6개 기준:

| 정책 | 기본 review 호출 |
| :--- | :--- |
| 현재 all non-owner | 12 |
| single peer | 6 |
| single peer + high risk 2개 escalation | 8 |
| one provider no peer | 0 또는 self-check 선택 시 6 |

기본 호출 수를 절반으로 줄이면서도 high-risk나 failed review에는 선택적으로 깊이를 줄 수 있다.

## 테스트 변경

수정/추가할 테스트:

1. 기존 `test_peer_review_planner_assigns_all_non_owner_reviewers_per_work_package`를
   `test_peer_review_planner_assigns_one_primary_non_owner_reviewer_by_default`로 변경한다.
2. active agent 1개일 때 `skipped_no_peer` 또는 `self_check` projection이 생성되는지 검증한다.
3. active agent 2개일 때 non-owner 1명만 reviewer가 되는지 검증한다.
4. active agent 3개일 때 reviewer priority가 deterministic한지 검증한다.
5. high-risk WP 또는 changes requested 결과에서 2차 review escalation 후보가 생성되는지 검증한다.
6. Execution Matrix가 `skipped`, `self-check`, `needs 2nd`를 표시하는지 검증한다.

## 구현 단위

1. `PeerReviewPlanner`에 review policy/depth 옵션 추가
2. review package planning contract 변경
3. skipped/self-check projection 추가
4. review escalation planner 추가
5. execution page review cell 표시 개선
6. report/export에서 skipped peer review를 명확히 표시

## 마이그레이션

기존 workflow session의 `review_packages`는 그대로 읽는다.

- 기존 session: planned reviewer가 2명 이상이면 그대로 표시
- 새 session: default one reviewer
- report에서는 legacy multi-review와 new selective-review를 모두 지원

## 리스크

- 리뷰 호출 수를 줄이면 결함 발견 확률이 낮아질 수 있다.
- 따라서 high-risk, failed, changes requested, security-sensitive 영역에서는 escalation을 쉽게 열어야 한다.
- UI가 `skipped`를 너무 조용히 보여주면 사용자가 검토가 없었다는 사실을 놓칠 수 있다.
- single provider 환경에서 self-check를 자동 실행하면 peer review 비용 절감 의도와 어긋날 수 있다.

## 결론

기본은 WP당 reviewer 1명으로 줄이고, provider 수와 risk에 따라 명확히 표시하는 정책이 적합하다.
이 변경은 실행 병렬성 목표와도 잘 맞는다. 실행은 가능한 병렬로 유지하고, 리뷰는 필요한 만큼만 호출해
전체 workflow latency와 provider 비용을 낮춘다.
