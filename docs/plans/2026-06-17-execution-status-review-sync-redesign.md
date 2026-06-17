# Execution Page Status/Review Sync Redesign

작성일: 2026-06-17
대상 branch/worktree: `docs/execution-sync-redesign` / `/home/user/workspace/Trinity-worktrees/execution-sync`

## 목적

실행 페이지가 각 work package(WP)의 실행 상태와 리뷰 상태를 얼마나 실시간으로
동기화하는지 분석하고, 동기화 비용이 과도해지지 않는 개선 방향을 정의한다.

이번 문서는 구현 전 설계 문서다. 실행 페이지 UI/UX와 리뷰 정책 변경은 별도 worktree의
문서에서 다룬다.

## 현재 동기화 경로

### 실행 status

실행 status는 provider를 계속 조회하는 방식이 아니다. 현재 흐름은 로컬 이벤트와
workflow session projection 기반이다.

1. `ExecutionProtocol`이 dependency-ready batch를 만들고 `asyncio.gather()`로 병렬 실행한다.
   - 근거: `src/trinity/workflow/execution.py`
   - `_plan_ready_batches()`가 safe parallel batch를 만들고, `run()`이 batch별로 병렬 dispatch한다.
2. WP 실행 시작 시 `WORK_PACKAGE_STARTED` 이벤트가 발생한다.
   - `package.status = WorkStatus.RUNNING`
   - `package.current_executor = agent_name`
3. WP 실행 완료 시 `WORK_PACKAGE_COMPLETED` 이벤트가 발생한다.
   - 결과 status, agent, summary, attempt chain, raw path가 event로 전달된다.
4. `TextualWorkflowController`가 background thread의 event bus를 poll한다.
   - 최근 이벤트는 최대 200개만 유지한다.
   - 시작/완료 이벤트는 workflow session에 기록된다.
5. `TrinityTextualApp`은 `set_interval(0.25, _poll_workflow_controller)`로 controller update를 drain한다.
6. 실행 페이지가 활성 route이면 `ExecutionMatrixScreen.apply_execution_state()`가 snapshot을 다시 받는다.

결론: 실행 status는 0.25초 poll 주기 안에서 준실시간으로 갱신된다. provider API를
추가 호출하지 않으므로 token/API 비용은 증가하지 않는다.

### review status

리뷰 status는 현재 실행 status만큼 실시간이 아니다.

1. 리뷰 대상은 `WorkflowEngine.ensure_review_packages()`와 `PeerReviewPlanner`가 만든다.
2. `ReviewExecutionProtocol.review_work_packages()`는 `REVIEW_START`와 `REVIEW_DONE` 이벤트만 emit한다.
3. 개별 review package의 시작/완료 이벤트는 현재 없다.
4. `TextualWorkflowController._start_review()`는 review thread가 끝난 뒤 `_review_results`를 한 번에 저장한다.
5. `NexusSnapshotAdapter._work_package_review_projections()`가 planned review와 completed result를 집계해
   `WorkPackageSnapshot.review_status`와 `reviewer_agent`를 만든다.

결론: 실행 페이지의 `Review` 컬럼은 planned/pending/reviewing/aggregate result를 보여줄 수 있지만,
현재 구조에서는 리뷰어별 실시간 진행 상태를 정확히 보여주지 않는다. 리뷰 작업 전체가 완료되기 전에는
대부분 `queued` 또는 `reviewing` 수준의 coarse status다.

## 현재 비용 분석

### 낮은 비용인 부분

- 0.25초 UI poll은 local memory/event queue drain 중심이다.
- provider CLI를 추가 호출하지 않는다.
- `NexusSnapshotAdapter.load_snapshot()`은 cache key를 사용한다.
  - session file stat
  - events file stat
  - shared context path stat
  - shared context가 64KB 이하일 때만 content fingerprint
  - config key
  - recent events key
- shared context가 큰 경우 전체 파일 hash를 매 poll마다 계산하지 않는다.

### 비용이 커질 수 있는 부분

- recent event key가 바뀌면 snapshot cache가 자주 깨진다.
- snapshot rebuild는 session과 workflow events를 다시 읽고 projection을 만든다.
- 이벤트 로그가 매우 커진 workflow에서는 `load_events_for_workflow()` 비용이 누적될 수 있다.
- 실행 페이지가 활성 route일 때 `apply_execution_state()`는 package list를 전부 remove/mount한다.
  WP 수가 많으면 렌더 비용이 커질 수 있다.
- review 상태를 더 촘촘하게 만들기 위해 이벤트를 많이 emit하면 UI re-render 빈도가 올라간다.

## 판단

현재 상태에서 실행 status 동기화 비용은 과도하지 않다. 0.25초 poll은 UX에는 충분히 빠르고,
provider/API 비용을 만들지 않는다.

다만 review status를 지금보다 실시간처럼 보이게 만들려면 단순히 poll interval을 줄이면 안 된다.
필요한 것은 더 많은 polling이 아니라 더 좋은 event granularity와 incremental rendering이다.

## 개선 사항

### 1. review 이벤트 세분화

다음 이벤트를 추가한다.

| 이벤트 | 의미 | UI 반영 |
| :--- | :--- | :--- |
| `REVIEW_PACKAGE_QUEUED` | 리뷰 계획 생성 | Review: `QUEUED` |
| `REVIEW_PACKAGE_STARTED` | 특정 WP/리뷰어 리뷰 시작 | Review: `RUN` 또는 `codex reviewing` |
| `REVIEW_PACKAGE_COMPLETED` | 특정 WP/리뷰어 리뷰 완료 | Review: `APPROVED`, `CHANGES`, `BLOCKED`, `FAILED` |
| `REVIEW_PACKAGE_SKIPPED` | 정책상 생략 | Review: `SKIP` 또는 tooltip/detail |

이벤트 payload:

```text
review_package_id
package_id
reviewer_agent
target_agent
status
summary
occurred_at
```

### 2. 실행 페이지 전용 lightweight projection

실행 페이지는 매번 full snapshot을 rebuild하지 않아도 된다. 다음 전용 projection을 둔다.

```text
ExecutionPageSnapshot
- workflow_id
- state
- target_workspace
- execution_run
- package_rows
- recent_activity
- issue_count
- retry_candidates
```

초기 route 진입 시에는 full snapshot을 쓰고, 이후 실행 중에는 event delta로 row만 갱신한다.

### 3. row-level update

현재 `ExecutionMatrixScreen._render_package_list()`는 전체 list를 remove/mount한다.
WP 수가 늘면 비용이 커진다. 다음 구조로 바꾼다.

- `package_id -> row widget` index 유지
- 상태/리뷰/로그 변경 시 해당 row의 label만 update
- package 추가/삭제가 있을 때만 list 구조 변경

### 4. poll interval 유지, event coalescing 추가

poll interval은 0.25초를 유지한다. 대신 한 tick 안의 이벤트를 합쳐 다음 단위로 한 번만 화면 갱신한다.

- package status changes
- review status changes
- activity feed append
- summary count update

### 5. 비용 guard

다음 guard를 둔다.

- 한 tick에서 최대 한 번만 execution page render
- recent activity는 기본 100개 memory cap, 화면에는 최근 8개만 노출
- workflow events file이 커지면 tail index 또는 persisted summary 사용
- shared context는 실행 페이지 poll path에서 읽지 않음

## UI에 노출할 동기화 의미

실행 페이지 문구는 사용자가 오해하지 않도록 다음처럼 정의한다.

- `RUN`: agent invocation이 시작됐고 완료 이벤트 전이다.
- `WAIT`: dependency, queue, review queue 등으로 아직 active invocation이 아니다.
- `REVIEW`: WP 실행은 끝났고 reviewer invocation 또는 review queue가 존재한다.
- `DONE`: 실행과 필수 리뷰가 완료됐다.
- `ISSUE`: 실행 실패, blocked, review changes required, review failed 중 하나다.

`Review` 컬럼은 reviewer 수에 따라 다음처럼 표시한다.

| 상태 | 표시 |
| :--- | :--- |
| 리뷰 없음 | `-` |
| 리뷰 예정 | `queued` |
| 리뷰 중 | `codex RUN` |
| 승인 | `approved` |
| 변경 요청 | `changes` |
| 생략 | `skipped` |

## 테스트 계획

1. execution event가 들어오면 0.25초 poll 안에 status row가 업데이트된다.
2. review package started/completed event가 들어오면 해당 WP의 review cell만 업데이트된다.
3. 100개 WP snapshot에서 status 하나 변경 시 full remount 없이 row label만 변경된다.
4. 1,000개 workflow event가 있어도 execution page refresh baseline이 50ms 이하를 유지한다.
5. review 이벤트가 없을 때 기존 coarse `queued/reviewing` fallback이 유지된다.

## 구현 단위

1. 이벤트 계약 추가
   - review package queued/started/completed/skipped
2. snapshot adapter projection 확장
   - review 진행 상태를 event 기반으로 fold
3. execution page row-level update
   - row id map과 incremental update
4. performance test
   - WP 100/500개, event 1,000개 baseline
5. 문서/README 갱신
   - execution status 의미 설명

## 리스크

- review event를 너무 잘게 만들면 UI는 좋아지지만 event log가 빨리 커질 수 있다.
- full snapshot과 event delta가 충돌하면 화면 상태가 session 상태와 어긋날 수 있다.
- review policy 변경과 동시에 진행하면 status semantics가 흔들릴 수 있으므로, selective review policy와
  status projection 계약을 먼저 맞춘 뒤 구현한다.
