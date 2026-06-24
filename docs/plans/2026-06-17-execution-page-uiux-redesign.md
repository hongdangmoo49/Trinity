# Execution Page UI/UX Redesign

작성일: 2026-06-17
대상 branch/worktree: `docs/execution-page-uiux-redesign` / `/home/user/workspace/Trinity-worktrees/execution-uiux`

## 목적

실행 페이지를 단순한 `Execution Matrix + raw log` 화면에서, 병렬 WP 실행과 리뷰 진행을
명확히 보여주는 운영 대시보드로 재설계한다.

이번 문서는 다음 분석을 UI/UX 개선 사항으로 수렴한다.

- status/review 상태가 실시간으로 동기화되는지
- 동기화 비용이 과도하지 않은지
- 각 agent가 WP를 병렬 실행하는 목표가 화면에 드러나는지
- WP 완료 후 review가 둘 다 필요한 것은 아니며, provider 수가 1개/2개인 경우도 자연스러운지

## 현재 화면 관찰

현재 `ExecutionMatrixScreen`은 다음 구조다.

```text
Header
Execution Matrix · workspace: <path>    [Expand Tasks]

Task | Assignee | Executor | Status | Review | Risk | Spec
...

Execution log
...
```

현재 장점:

- owner와 executor가 분리되어 fallback 실행을 볼 수 있다.
- `Status`는 Nexus와 같은 compact label(`RUN`, `WAIT`, `DONE`, `ISSUE`)을 사용한다.
- `Review`, `Risk`, `Spec` 컬럼이 존재한다.
- `Spec` 버튼으로 WP 상세를 열 수 있다.

현재 문제:

- 좁은 터미널에서 `Review`, `Risk`, `Spec` 컬럼이 밀려 보이지 않는다.
- 상단에 실행 요약이 없어 현재 몇 개가 실행 중/대기/실패인지 바로 알기 어렵다.
- raw execution log가 화면 대부분을 차지해 핵심 상태보다 로그가 더 강조된다.
- `Review` 컬럼은 실제 reviewer별 진행을 보여주기에는 정보가 부족하다.
- `/execute-retry` 같은 회복 액션을 사용자가 기억해야 한다.
- provider가 1개 또는 2개일 때 peer review의 의미가 UI에 드러나지 않는다.

## 사용자 모델

실행 페이지 사용자는 다음 질문에 즉시 답을 얻고 싶다.

1. 지금 어떤 WP가 실제로 실행 중인가?
2. 어떤 agent가 실행하고 있고, fallback이 있었는가?
3. 병렬 실행 batch가 어떻게 나뉘었는가?
4. 끝난 WP는 리뷰 중인가, 리뷰를 통과했는가?
5. 문제가 있으면 내가 눌러야 할 다음 액션은 무엇인가?
6. provider가 부족해서 리뷰가 생략된 것인지, 리뷰가 승인된 것인지 구분되는가?

## 개선 방향

### 1. 실행 요약 바

상단 header 아래에 1줄 요약 바를 둔다.

```text
RUN 2 · REVIEW 1 · WAIT 3 · DONE 4 · ISSUE 1    batch 2/4    target: ~/project
```

포함 정보:

- status count
- review count
- current batch
- target workspace
- recovery state
- retry candidate count

이 요약은 execution page가 열렸을 때 가장 먼저 읽히는 정보여야 한다.

### 2. 병렬 batch lane 표시

병렬 실행 목표를 화면에 드러내려면 단순 row list보다 batch/lane 표현이 필요하다.

권장 compact 표현:

```text
Batch 1  [WP-001 Codex RUN] [WP-002 Claude RUN]
Batch 2  [WP-003 WAIT dep: WP-001] [WP-004 WAIT]
Review   [WP-005 Antigravity RUN]
```

넓은 화면에서는 lane을 카드처럼 보여주고, 좁은 화면에서는 batch header + row list로 접는다.

### 3. 반응형 row 모드

현재 모든 컬럼을 고정 폭으로 표시한다. 대신 viewport 폭에 따라 모드를 나눈다.

#### Compact mode: 80 columns

```text
WP-001 RUN  Codex  README Nexus visual assets...
       review: Antigravity queued · risk: low · spec: Enter
```

표시 우선순위:

1. WP id
2. status
3. executor
4. task title
5. review/risk/action second line

#### Standard mode: 120 columns

```text
WP      Task                         Owner   Executor       Status  Review          Risk  Action
WP-001  README Nexus visuals...      codex   codex          RUN     Agy queued      low   Spec
```

#### Wide mode: 150+ columns

추가 정보:

- dependency
- parallel group
- retry state
- files changed count

### 4. Status semantics 확장

기존 `WAIT`가 너무 많은 상태를 포함한다. 실행 페이지에서는 더 구체적인 stage를 제공한다.

| Raw state | Primary label | Secondary label |
| :--- | :--- | :--- |
| `pending` | `WAIT` | `queued` |
| dependency blocked | `WAIT` | `dep: WP-001` |
| `running` | `RUN` | executor |
| `needs_review` | `REVIEW` | queued/running reviewer |
| `done` | `DONE` | reviewed/accepted |
| `blocked`, `failed` | `ISSUE` | retryable/blocker |

Nexus와의 통일을 위해 primary label은 compact하게 유지하고, 실행 페이지에서만 secondary label을 추가한다.

### 5. Review cell 재설계

선택형 리뷰 정책을 반영한다.

| 상황 | Review cell |
| :--- | :--- |
| provider 1개 | `SKIP no peer` |
| provider 1개 + self check | `SELF RUN/DONE` |
| provider 2개 | `Claude WAIT/RUN/DONE` |
| provider 3개 기본 | `Agy WAIT/RUN/DONE` |
| 2차 리뷰 필요 | `needs 2nd` |
| 2차 리뷰 진행 | `Claude 2nd RUN` |
| changes requested | `CHANGES` |
| blocked/failed review | `ISSUE` |

중요: 리뷰가 없었던 상태와 리뷰 승인 상태는 절대 같은 색/라벨로 보이면 안 된다.

### 6. Activity Feed로 로그 축소

raw log는 기본 화면에서 5-8개 최근 이벤트만 보여준다.

```text
Activity
10:42 WP-001 started by Codex
10:43 WP-002 waiting on WP-001
10:45 WP-001 done, review queued for Antigravity
10:47 WP-003 blocked: missing npm
```

전체 로그는 별도 액션으로 연다.

- `L`: full log modal
- `/report`: report screen
- `Spec`: WP별 raw output

### 7. 문제 상태 액션 노출

ISSUE가 있는 경우 상단 또는 row에 직접 액션을 제공한다.

```text
Issues: 2    [Retry failed] [Open blocked] [Mark interrupted] [Abort run]
```

row별:

```text
WP-004 ISSUE  retryable  [Retry] [Spec]
```

단축키/명령을 기억하지 않아도 회복 동선이 보여야 한다.

### 8. WP 상세 모달 재구성

현재 상세 모달은 Markdown 일괄 출력이다. 실행 페이지에서는 다음 순서가 더 좋다.

```text
WP-001 README Nexus visual assets

Summary
- Status: RUN
- Owner: Codex
- Executor: Codex
- Review: Antigravity queued
- Risk: low

Result
- Last result summary
- Changed files
- Blockers

Review
- Review plan
- Review result
- Required changes

Spec
- Objective
- Scope
- Acceptance criteria
- Expected files
```

실행 중에는 `Summary/Result/Review`를 먼저 보여주고, 설계 spec은 뒤로 내린다.

## 실시간 동기화 UX

실행 status는 현재도 0.25초 poll과 event bus로 준실시간 갱신된다. 이 구조는 provider 호출을
늘리지 않으므로 비용이 낮다.

UI 문구:

```text
Live from local workflow events
```

단, review status는 현재 coarse 상태만 가능하다. reviewer별 실시간 표시를 하려면 다음 이벤트가 필요하다.

- `REVIEW_PACKAGE_QUEUED`
- `REVIEW_PACKAGE_STARTED`
- `REVIEW_PACKAGE_COMPLETED`
- `REVIEW_PACKAGE_SKIPPED`

이벤트 없이 poll 주기만 줄이는 개선은 금지한다. 비용만 늘고 정확도는 크게 좋아지지 않는다.

## Provider 수별 UI 상태

### provider 1개

```text
Review: SKIP no peer
Hint: Enable another provider for peer review.
```

선택적으로 self-check가 켜져 있으면:

```text
Review: SELF CHECK
```

### provider 2개

```text
Review: Claude queued
```

선택지가 없으므로 reviewer picker를 보여주지 않는다.

### provider 3개

```text
Review: Antigravity queued
```

2차 리뷰가 필요한 경우만:

```text
Review: needs 2nd
Action: Request second review
```

## 구현 후보

### Phase 1 - 화면 정보 구조 개선

- execution summary bar 추가
- status count와 review count 표시
- activity feed를 raw log보다 위에 배치
- row compact/standard mode 도입

### Phase 2 - 선택형 리뷰 UI 반영

- `SKIP no peer`, `SELF`, `needs 2nd` label 추가
- review cell renderer 분리
- WP detail modal에 Review Plan 추가

### Phase 3 - 실시간 review 이벤트

- review queued/started/completed/skipped event 추가
- event delta 기반 row update
- full remount 최소화

### Phase 4 - action surface

- Retry failed
- Open blocked
- Request second review
- Full log
- Spec

## 테스트 계획

1. `80x24`에서 Review/Risk/Action이 화면 밖으로 밀리지 않는다.
2. `120x36`에서 summary bar, rows, activity feed가 모두 보인다.
3. WP 100개에서 status 1개 변경 시 row-level update만 발생한다.
4. provider 1개 snapshot은 `SKIP no peer`를 보여준다.
5. provider 2개 snapshot은 non-owner reviewer 1명을 보여준다.
6. provider 3개 snapshot은 primary reviewer 1명만 보여준다.
7. high-risk escalation snapshot은 `needs 2nd`를 보여준다.
8. review started/completed event가 들어오면 Review cell이 갱신된다.
9. execution log가 길어져도 화면에는 최근 activity만 제한 노출된다.
10. keyboard-only 사용자가 `Spec`, `Retry`, `Full log`에 접근할 수 있다.

## 문서화할 개선 사항 체크리스트

2026-06-24 기준 최신 상태:

- [x] 실행 status는 workflow event/snapshot 기반 준실시간이며 provider 호출 비용을 만들지 않는다.
- [x] poll interval을 줄이는 대신 snapshot event tail, event index cache, row-level rendering으로 갱신 비용을 낮춘다.
- [x] execution log가 길어져도 화면 projection은 bounded activity로 제한한다.
- [x] large workflow snapshot projection이 full event scan으로 회귀하지 않도록 performance budget test를 둔다.
- [ ] review status는 아직 coarse하다. reviewer별 queued/started/completed/skipped 실시간 상태는 이벤트 추가가 필요하다.
- [ ] 기본 reviewer 수를 1명으로 줄이는 선택형 리뷰 정책을 반영한다.
- [ ] provider 1개/2개/3개 UI 표현을 분리한다.
- [ ] 병렬 실행 batch/lane을 화면에 노출한다.
- [ ] 문제 상태에서 사용자 액션을 표면화한다.

## 리스크

- 정보량을 늘리면 좁은 터미널에서 다시 깨질 수 있다. compact mode를 먼저 설계해야 한다.
- review policy와 UI를 동시에 바꾸면 테스트 범위가 커진다. policy와 renderer를 분리해 구현한다.
- 실시간 이벤트를 많이 추가하면 event log가 커질 수 있다. activity feed cap과 event compaction이 필요하다.
- review skipped 표시가 너무 작으면 사용자가 peer review 부재를 놓칠 수 있다.

## 결론

실행 페이지의 핵심 UX는 “무엇이 병렬로 실행 중이고, 무엇이 리뷰/문제/대기 상태인지”를 즉시 알려주는 것이다.
현재 화면은 필요한 데이터는 대부분 갖고 있지만, 정보 구조와 표시 우선순위가 부족하다. 다음 구현은
summary bar, responsive row, activity feed, selective review label을 우선 적용하는 것이 좋다.
