# Nexus Progress Visibility Redesign

작성일: 2026-06-16

브랜치: `feature/nexus-progress-visibility`

상태: 설계 완료

## 배경

이전 작업에서 Nexus 중앙 영역은 대화형 요약과 질문 패널 중심으로 정리되었다. 다음 병목은
"지금 무엇이 돌아가고 있는지"를 한눈에 파악하기 어렵다는 점이다.

현재 구조의 한계는 다음과 같다.

- provider card가 세로로 길고 스크롤 카드처럼 보여 상단 공간을 많이 차지한다.
- provider 상태는 `Running`, `Queued`, `Idle`, `Ready`, `Done` 같은 원문을 거의 그대로 표시해 시각적 위계가 약하다.
- running 애니메이션은 작은 spinner 문자 중심이라 상태 변화가 눈에 잘 들어오지 않는다.
- 우측 Inspector의 `Packages`는 단순 리스트라 진행률, 현재 실행 WP, 다음 대기 WP, 막힌 WP를 빠르게 구분하기 어렵다.
- 중앙 `Work Packages` 요약은 개수 중심이라 execution 단계에서 "현재 어디까지 왔는지"는 충분히 드러나지 않는다.

## 목표

1. provider card를 더 compact하게 만들고 상단 provider strip 높이를 줄인다.
2. provider 상태를 짧은 라벨과 색상으로 명확히 구분한다.
3. work package 진행률을 중앙 또는 우측 Inspector 상단에서 즉시 확인할 수 있게 한다.
4. "현재 진행 중 WP", "다음 대기 WP", "막힌 WP"를 한눈에 보이게 구성한다.
5. 기존 workflow engine, session 저장 포맷, execution 정책은 변경하지 않는다.

## 비목표

- provider 호출 방식이나 상태 전이 정책을 바꾸지 않는다.
- WorkPackage 저장 schema를 마이그레이션하지 않는다.
- Execution Matrix 페이지를 재설계하지 않는다.
- 복잡한 그래프/간트 차트를 도입하지 않는다.

## 현재 구현 기준

### Provider Panel

`ProviderPanel`은 현재 다음 4줄을 렌더한다.

- provider name
- provider cli/provider id
- status line: `Running · Enabled`
- summary

CSS 기준:

- `#provider-strip`: height 8
- `.provider-panel`: height 8, `VerticalScroll`
- running이면 `.provider-running` class만 추가
- disabled이면 `.provider-disabled` class만 추가

### Inspector

`WorkflowInspector`는 현재 다음 섹션을 순서대로 렌더한다.

- Workflow
- Providers
- Questions
- Decisions
- Packages
- Post Review
- Execution Log

`Packages`는 `snapshot.work_packages`의 앞 5개만 단순 bullet로 보여준다. `snapshot.work_package_details`는 이미
상세 필드를 갖고 있지만 Inspector 상단 요약에는 사용되지 않는다.

### Snapshot에서 쓸 수 있는 정보

`WorkPackageSnapshot`에는 다음 UI projection에 필요한 필드가 이미 있다.

- `id`, `title`, `owner_agent`, `status`
- `current_executor`, `last_executor`
- `risk`
- `dependencies`
- `repair_blocked_reason`, `repair_attempt_count`, `repair_max_attempts`
- `last_result_status`, `last_result_summary`, `last_result_blockers`
- `review_status`, `reviewer_agent`, `review_summary`

따라서 이번 작업은 새 persistence 없이 Textual UI helper에서 계산해도 충분하다.

## UX 계약

### Provider Card

상단 provider card는 4~5줄 높이로 줄인다.

예시:

```text
Claude        RUN
claude-code   opus[1m]
요약 한 줄...
```

또는 좁은 화면에서는 다음처럼 한 줄에 압축한다.

```text
Claude RUN · opus[1m]
요약 한 줄...
```

상태 라벨은 provider 원문 status를 정규화해 표시한다.

| 원문/상태 | 표시 라벨(영문) | 표시 라벨(한글) | 색상/클래스 | 의미 |
| --- | --- | --- | --- | --- |
| `running`, `executing`, `reviewing`, `deliberating` | `RUN` | `실행` | warning/accent + animation | 현재 작업 중 |
| `queued`, `pending`, `waiting` | `WAIT` | `대기` | muted/primary | 차례 대기 |
| `idle` | `IDLE` | `휴식` | dim | 이번 턴 대상 아님 |
| `ready`, `done`, `completed`, `success` | `DONE` | `완료` | success | 응답/작업 완료 |
| `blocked`, `failed`, `error`, `timeout` | `ISSUE` | `문제` | error | 개입/재시도 필요 |
| disabled agent | `OFF` | `끔` | muted dim | 비활성 |

라벨은 짧아야 하며, 상세 status 원문은 tooltip 또는 Inspector에서 확인한다.

### Work Package Progress Summary

우측 Inspector 최상단에 `Progress` 섹션을 추가한다.

예시:

```text
Progress
8 WP · 2 done · 1 running · 4 waiting · 1 blocked
[##>.....!]
```

텍스트 바 규칙:

- `#`: done
- `>`: running
- `.`: pending/waiting
- `!`: blocked/failed
- `?`: unknown

폭은 Inspector 너비를 고려해 최대 12~16칸으로 제한한다.

### Current / Next / Blocked

Inspector의 Packages 영역은 단순 리스트 대신 세 그룹을 우선한다.

```text
Current
- WP-002 Codex · Parser

Next
- WP-003 Claude · Output renderer
- WP-004 Agy · Validation target

Blocked
- WP-007 Codex · API adapter
  repair 2/2 · missing credentials
```

우선순위:

1. `status == running` 또는 `current_executor`가 있는 WP
2. `status == blocked`, `repair_blocked_reason`, `last_result_status in {blocked, failed}`가 있는 WP
3. `status in {pending, queued, waiting}`인 WP
4. `status == done`은 summary count에는 포함하되 list에는 기본적으로 숨긴다.

`Next`는 처음 3개만 보여주고, 나머지는 `+N more`로 표시한다.

### Central Area

중앙 `Work Packages` 요약은 지금처럼 상세 WP를 나열하지 않는다. 다만 execution 상태에서는 progress count를 더 직접적으로 보여준다.

예시:

```text
작업 패키지
- 8개 작업 패키지 · done=2, running=1, pending=4, blocked=1
- 현재: WP-002 Codex · Parser
- 막힘: WP-007 Codex · API adapter
- 상세 설계와 WP 목록은 Inspector 또는 Report에서 확인하세요.
```

중앙은 여전히 판단과 다음 액션 중심이고, 상세 리스트는 Inspector에 둔다.

## 구현 계획

### 1. ProviderPanel compact화

- `ProviderPanel`에 상태 정규화 helper를 추가한다.
- `ProviderPanelState` 또는 `ProviderPanel` 생성자에 `lang`을 전달할 수 있게 한다.
- status line을 `raw status · enabled`에서 짧은 chip style 문자열로 변경한다.
- card height를 8에서 5 또는 6으로 줄이고 `VerticalScroll`이 필요 없으면 일반 `Vertical`로 바꾸는 것을 검토한다.
- summary는 한두 줄로 제한하고 raw output은 계속 Provider Inspector에서만 확인한다.

### 2. Provider 상태 class 체계 추가

- 기존 `.provider-running`, `.provider-disabled` 외에 다음 class를 추가한다.
  - `.provider-state-running`
  - `.provider-state-waiting`
  - `.provider-state-idle`
  - `.provider-state-done`
  - `.provider-state-issue`
  - `.provider-state-off`
- CSS에서 border/text color를 다르게 지정한다.
- running 상태에서는 기존 activity frame을 chip 앞에 붙이거나 card 오른쪽에 표시한다.

### 3. WP progress helper 추가

새 helper를 둘 중 하나로 둔다.

- `src/trinity/textual_app/widgets/progress_summary.py`
- 또는 `WorkflowInspector` 내부 private helper

초기 구현은 결합도를 낮추기 위해 작은 pure helper 함수로 시작한다.

필요 함수:

- `work_package_counts(details) -> dict[str, int]`
- `current_work_packages(details, limit=3)`
- `next_work_packages(details, limit=3)`
- `blocked_work_packages(details, limit=3)`
- `progress_bar(counts, width=12)`
- `compact_wp_line(package)`

### 4. Inspector 상단 개편

`WorkflowInspector.compose()` 순서를 다음으로 바꾼다.

1. Progress
2. Current
3. Next
4. Blocked
5. Workflow
6. Providers
7. Questions
8. Decisions
9. Post Review
10. Execution Log

`Packages` 섹션은 `Current/Next/Blocked`으로 대체한다.

### 5. Central WP summary 보강

`CentralAgentView._append_work_package_overview()`는 이미 개별 WP 나열을 숨긴다. 여기에 다음 정보를 추가한다.

- current 1개
- blocked 1개
- progress counts

단, 중앙이 다시 과밀해지지 않도록 각 항목은 최대 1줄만 표시한다.

## 테스트 계획

### ProviderPanel

- `Running` status가 `RUN` 또는 `실행` chip으로 정규화된다.
- `Queued/Pending/Waiting`은 waiting class를 받는다.
- `Idle`은 idle class를 받는다.
- `Ready/Done/Completed`는 done class를 받는다.
- `Failed/Blocked/Timeout`은 issue class를 받는다.
- disabled provider는 off class와 disabled style을 유지한다.

### Inspector

- running/pending/blocked/done WP가 섞인 snapshot에서 Progress count가 정확하다.
- Current 섹션은 running WP만 표시한다.
- Next 섹션은 pending WP를 최대 3개 표시하고 나머지는 `+N more`를 표시한다.
- Blocked 섹션은 blocked/failed/repair blocked WP를 표시한다.
- done WP는 summary count에는 들어가지만 Current/Next/Blocked list에는 기본 노출되지 않는다.

### Central

- executing snapshot에서 `작업 패키지` 요약에 counts가 나온다.
- current/blocked가 있으면 중앙에 각각 1줄만 표시된다.
- 개별 WP 전체 목록은 중앙에 다시 노출되지 않는다.

### Regression

- 기존 질문 패널, blueprint action, slash command local result 테스트가 깨지지 않는다.
- `tests/test_textual_app.py`, `tests/test_central_agent_view.py`, `tests/test_textual_smoke.py`를 최소 검증으로 돌린다.

## 구현 리스크

- Textual CSS에서 작은 카드 height가 너무 작으면 summary가 잘릴 수 있다. summary는 의도적으로 짧게 자르되, Provider Inspector에서 원문을 계속 볼 수 있게 한다.
- status 원문이 provider마다 다를 수 있으므로 정규화 helper는 unknown fallback을 가져야 한다.
- pending WP의 dependency readiness는 현재 snapshot에 직접 계산되어 있지 않다. `Next`는 일단 `pending/queued/waiting`을 단순 후보로 보여주고, dependency-ready 계산은 후속 작업으로 남긴다.
- Inspector가 너무 많은 섹션을 가지면 다시 복잡해질 수 있다. Progress/Current/Next/Blocked를 상단에 두고 기존 Decisions/Execution Log는 하단으로 밀어 우선순위를 분명히 한다.

## 완료 기준

- provider strip 높이가 줄고 각 provider card가 compact하게 보인다.
- provider status가 짧은 라벨과 색상 class로 구분된다.
- 우측 Inspector 상단에서 WP 진행률과 current/next/blocked를 확인할 수 있다.
- 중앙 Work Packages 요약이 progress count와 핵심 current/blocked만 보여준다.
- 관련 테스트가 추가되고 통과한다.

