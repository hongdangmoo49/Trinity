# Execute Retry and Work Package Detail Design

작성일: 2026-06-08

브랜치: `codex/execution-resume-recovery-design`

상태: 구현 완료 (`0.11.0`)

## 목적

현재 execution recovery 구현은 `/execute` 실행 중 TUI가 종료되거나 worker가 사라진
상황을 감지하고, interrupted/running/blocked/failed package를 다시 시작할 수 있게 하는
1차 복구 흐름을 제공한다.

다음 단계에서는 `/execute-retry`를 독립 slash command로 추가한다.

1. 실행 중단 복구뿐 아니라, 정상적으로 실행이 끝난 뒤 `failed` 또는 `blocked`로 남은 WP도
   사용자가 나중에 명시적으로 재시작할 수 있게 한다.
2. Textual에서는 `/execute-retry` 입력 시 중앙 modal을 띄우고, 사용자가 retry 범위를 선택한다.
3. retry 범위는 `all`, `failed`, `blocked`, `interrupted`, `custom`으로 제공한다.
4. `custom` 선택 시 같은 modal 안에서 WP 목록 옆에 체크박스를 표시한다.
5. execution 페이지에서 각 WP의 상세 설계도를 즉시 확인할 수 있게 한다.
6. 완료된 WP를 실수로 재실행하지 않는 원칙은 유지한다.

## 현재 상태 요약

### 이미 구현된 것

- `WorkflowSession.execution_run` metadata
- `WorkPackage.current_executor`, `last_executor`
- stale execution 감지:
  - `WorkflowEngine.detect_interrupted_execution()`
- recovery action:
  - `retry_interrupted_execution()`
  - `mark_interrupted_execution()`
  - `abort_interrupted_execution()`
- Textual `/resume` 후 recovery 표시
- Textual `/execute` 기본 입력 시 stale recovery guard
- Plain TUI `/execute retry`, `/execute mark-interrupted`, `/execute abort`
- Execution Matrix `Assignee` / `Executor` 컬럼 분리
- 환경 검증 blocker 자동 fallback 억제

### 현재 한계

기존 `/execute retry`는 이름과 UX상 일반 재시도처럼 보이지만, 실제 구현은
interrupted recovery summary가 있는 경우에 가장 잘 맞춰져 있다.

완전히 실행이 종료된 뒤 workflow state가 `failed`가 되었고 WP status가 `failed`로 남은
경우에는 recovery summary가 없을 수 있다. 이 경우 사용자가 나중에 retry를 원해도
재시작 대상으로 잡히지 않는 경로가 생긴다.

또한 execution 페이지에는 WP 상태 요약만 보이고, 각 WP의 구체적인 설계 정보
`objective`, `scope`, `expected_files`, `acceptance_criteria`, `dependencies`,
`risk`, `repair_notes`, 이전 실행 결과를 바로 볼 수 있는 UI가 없다.

## 용어

| 용어 | 의미 |
| :--- | :--- |
| retryable WP | 사용자가 명시적으로 다시 실행할 수 있는 WP |
| interrupted retry | stale execution에서 `running`으로 남은 WP 재시도 |
| failed retry | 실행 결과가 `failed`인 WP 재시도 |
| blocked retry | 실행 결과가 `blocked`인 WP 재시도 |
| custom retry | 사용자가 체크박스로 직접 선택한 WP만 재시도 |
| detail view | execution 페이지에서 WP 상세 설계와 실행 기록을 보여주는 view/modal |

## `/execute-retry` 명령 설계

### 기본 원칙

1. `/execute-retry`는 provider process reattach가 아니다.
2. Textual에서는 명령 입력 즉시 실행하지 않고 중앙 retry modal을 연다.
3. 사용자가 modal에서 범위와 대상을 확인하고 `Retry selected`를 눌러야 실행된다.
4. retry는 새 one-shot execution run을 시작한다.
5. 기본 retry 대상은 `running`, `failed`, `blocked` WP다.
6. `done`, `needs_review` WP는 기본적으로 재실행하지 않는다.
7. active worker가 살아 있으면 retry를 거부한다.
8. target workspace가 없으면 기존 `/execute`처럼 preflight를 먼저 요구한다.
9. retry 전 기존 execution result는 삭제하지 않는다. 새 결과가 같은 package id로 upsert되더라도
   event log와 raw artifact path는 이전 시도 기록을 보존한다.

### 명령 형태

| 명령 | Textual 동작 | Plain TUI 동작 |
| :--- | :--- | :--- |
| `/execute-retry` | 중앙 retry modal을 연다. 기본 filter는 `all`이다. | retryable WP 전체 plan을 출력하고 확인 후 실행한다. |
| `/execute-retry all` | modal을 열고 `all` filter를 선택해 둔다. | retryable WP 전체를 재시도한다. |
| `/execute-retry failed` | modal을 열고 `failed` filter를 선택해 둔다. | `failed` WP만 재시도한다. |
| `/execute-retry blocked` | modal을 열고 `blocked` filter를 선택해 둔다. | `blocked` WP만 재시도한다. |
| `/execute-retry interrupted` | modal을 열고 `interrupted` filter를 선택해 둔다. | stale recovery의 `running` WP만 재시도한다. |
| `/execute-retry custom` | modal을 열고 `custom` filter를 선택한다. WP row 옆 체크박스가 보인다. | WP id 직접 입력 안내를 표시한다. |
| `/execute-retry WP-001 WP-003` | modal을 열고 `custom` filter와 해당 WP 체크 상태를 적용한다. | 지정한 WP만 재시도한다. |

기존 `/execute retry`와 `/execute retry-interrupted`는 한 릴리스 동안 compatibility alias로
처리할 수 있지만, help와 palette에는 `/execute-retry`를 primary로 노출한다.

### retryable 판단

기본 retryable status:

- `WorkStatus.RUNNING`
- `WorkStatus.FAILED`
- `WorkStatus.BLOCKED`

상황별 처리:

| 현재 workflow state | retry 허용 | 설명 |
| :--- | :--- | :--- |
| `executing` + worker 없음 | 허용 | stale recovery로 보고 `running` 포함 |
| `failed` | 허용 | failed WP를 재시도 대상으로 잡고 state를 execution-ready로 되돌림 |
| `needs_user_decision` | 허용 | blocked WP를 사용자가 명시적으로 다시 시도할 수 있음 |
| `blueprint_ready` | 허용 | 이전 실패/blocked package가 있으면 retry 가능 |
| `reviewing`, `done` | 기본 거부 | 완료 또는 리뷰 단계에서 기본 retry는 혼란을 만든다. 추후 force 옵션으로 확장 가능 |
| active worker running | 거부 | 동시에 두 execution worker를 만들지 않음 |

### retry 대상 결정 알고리즘

1. active worker가 있으면 중단한다.
2. `detect_interrupted_execution(worker_running=False)`를 호출해 stale running 상태를 먼저 확정한다.
3. modal filter 또는 Plain TUI args를 retry selector로 정규화한다.
4. 후보 목록을 만든다.
   - `all`: `running`, `failed`, `blocked`
   - `failed`: `failed`
   - `blocked`: `blocked`
   - `interrupted`: stale recovery의 `running`
   - `custom`: 체크된 WP id 또는 명시적으로 입력된 WP id
5. 후보에서 `done`, `needs_review`, `requires_execution=False`는 제외한다.
6. 후보가 비어 있으면 modal 또는 local command result로 이유를 표시한다.
7. 사용자가 확인하면 후보 WP를 `pending`으로 변경한다.
8. `current_executor`를 비우고 `last_executor`는 보존한다.
9. retry event를 기록한다.
10. target workspace가 없으면 preflight를 연다.
11. target workspace가 있으면 새 execution run을 시작한다.

## Execute Retry Modal UX

모달은 화면 중앙에 뜬다. 첫 진입 시 한 화면에서 retry scope와 WP 목록을 모두 보여준다.
`custom`을 눌러도 다른 depth나 별도 화면으로 들어가지 않는다. 같은 모달의 WP 목록 옆에
체크박스가 나타난다.

```text
Execute Retry

Target: /home/user/workspace/game
Recovery: interrupted

[ All ] [ Failed ] [ Blocked ] [ Interrupted ] [ Custom ]

  WP       Status       Topic                         Owner   Executor
  WP-001   failed       Client input controller        codex   claude fallback
  WP-002   blocked      Asset pipeline                 claude  -
  WP-003   done         Shared protocol contracts      codex   codex

Selected: WP-001, WP-002

[Cancel] [Retry selected]
```

Custom 선택 시:

```text
Execute Retry

[ All ] [ Failed ] [ Blocked ] [ Interrupted ] [ Custom ]

  Use   WP       Status       Topic                         Owner   Executor
  [x]   WP-001   failed       Client input controller        codex   claude fallback
  [ ]   WP-002   blocked      Asset pipeline                 claude  -
  [-]   WP-003   done         Shared protocol contracts      codex   codex

Selected: WP-001

[Cancel] [Retry selected]
```

### 모달 선택 규칙

- `all`, `failed`, `blocked`, `interrupted`, `custom`은 segmented control 또는 버튼 그룹으로 표시한다.
- `all`, `failed`, `blocked`, `interrupted`에서는 WP row 옆 체크박스를 숨긴다.
- `custom`에서는 WP row 옆 체크박스를 표시한다.
- `custom`으로 전환하면 직전 filter의 selected WP를 초기 체크 상태로 유지한다.
- retryable WP는 체크 가능하다.
- `done`, `needs_review`, `requires_execution=False` WP는 disabled 상태로 표시한다.
- disabled row는 체크박스 대신 `[-]` 또는 비활성 체크박스를 표시한다.
- disabled 이유는 tooltip 또는 우측 note로 표시한다.
- 선택 가능한 WP가 없으면 `Retry selected` 버튼을 disabled 처리한다.

WP topic은 다음 순서로 짧게 만든다.

1. `WorkPackage.title`
2. 없으면 `objective` 첫 문장
3. 그래도 없으면 WP id

## Engine API 변경안

현재 `retry_interrupted_execution()`은 interrupted recovery에 이름과 책임이 묶여 있다.
새 API를 추가하고 기존 메서드는 wrapper로 유지한다.

```python
@dataclass(frozen=True)
class RetrySkip:
    package_id: str
    status: str
    reason: str

@dataclass(frozen=True)
class ExecutionRetryPlan:
    selector: str
    requested: tuple[str, ...]
    selected: tuple[str, ...]
    skipped: tuple[RetrySkip, ...]
    target_workspace: Path | None

def build_execution_retry_plan(
    self,
    selector: str = "all",
    package_ids: Iterable[str] = (),
) -> ExecutionRetryPlan:
    ...

def prepare_execution_retry(
    self,
    selector: str = "all",
    package_ids: Iterable[str] = (),
) -> ExecutionRetryPlan:
    ...

def retry_interrupted_execution(self) -> dict[str, Any] | None:
    # Backward-compatible wrapper.
    plan = self.prepare_execution_retry(selector="interrupted")
    return self.execution_recovery_summary() if plan.selected else None
```

`prepare_execution_retry()`는 실제 상태 변경을 수행한다.

상태 변경:

- selected WP status -> `pending`
- selected WP current_executor -> `""`
- `session.execution_run.state` -> `retry_requested`
- `session.execution_run.retry_packages` -> selected ids
- workflow state -> `blueprint_ready`

## 이벤트 설계

기존 `work_package_retry_requested`는 유지한다.

추가 이벤트:

| Event | Payload | 목적 |
| :--- | :--- | :--- |
| `execution_retry_planned` | `selector`, `requested`, `selected`, `skipped`, `target_workspace` | UI와 report에서 retry plan을 설명 |
| `work_package_retry_requested` | `package_id`, `previous_status`, `agent`, `reason` | 개별 WP 재시도 기록 |
| `execution_run_started` | 기존 payload 유지 | 실제 새 run 시작 |

`skipped` 예시:

```json
{
  "package_id": "WP-002",
  "status": "done",
  "reason": "done packages are not retried by default"
}
```

## Textual controller 변경안

`/execute-retry`는 `/execute`의 subcommand가 아니라 별도 local execution command로
라우팅한다.

`TextualWorkflowController`에는 plan 생성과 실행 준비를 분리한 메서드를 둔다.

```python
def preview_execution_retry(
    self,
    selector: str = "all",
    package_ids: Iterable[str] = (),
) -> TextualExecutionRetryPreview:
    ...

def confirm_execution_retry(
    self,
    selector: str = "all",
    package_ids: Iterable[str] = (),
) -> TextualWorkflowOutcome:
    ...
```

Textual event flow:

```text
User types /execute-retry
  -> TrinityTextualApp opens ExecuteRetryModal(center)
  -> modal requests preview plan from controller
  -> user selects all/failed/blocked/interrupted/custom
  -> modal updates selected WP list in-place
  -> user presses Retry selected
  -> app calls confirm_execution_retry(...)
  -> target missing: open execute preflight
  -> target present: start execution
```

`request_execution()`은 기존 `/execute`의 preflight/normal execution을 유지한다.
stale recovery guard도 `/execute` 기본 입력에서 계속 동작한다.
`/execute-retry`는 사용자가 명시적으로 선택한 action이므로 recovery guard에 막히지 않는다.

## Plain TUI 변경안

`TrinitySession`에는 `_cmd_execute_retry(args)`를 추가한다. Plain TUI에는 중앙 modal이
없으므로 같은 selection 정책을 table과 confirmation prompt로 표현한다.

출력:

```text
Execute Retry
Mode: all
Selected: WP-001, WP-003
Skipped: WP-002 done
Target: /home/user/workspace/game
```

target workspace가 없으면 기존 안내를 출력한다.

## Slash command registry

새 command를 등록한다.

```text
/execute-retry [all|failed|blocked|interrupted|custom|WP-ID...]
```

한국어 summary:

```text
실패하거나 중단된 작업 재시도
```

## Execution 페이지 WP 상세 설계 보기

### 요구

execution 페이지의 각 WP row에 상세 보기 버튼을 추가한다. 사용자는 실행 중이거나 실패한 WP의
구체적인 설계와 이전 결과를 바로 확인할 수 있어야 한다.

### UI 결정

Textual `DataTable`은 cell 안에 실제 `Button` widget을 mount하는 구조가 아니다. 사용자가
말한 "row에 버튼"을 실제 버튼으로 구현하려면 execution matrix를 `DataTable` 단독 구조에서
row widget list 구조로 바꾸는 편이 맞다.

권장 구조:

```text
Execution Matrix

Task                 Assignee  Executor          Status   Risk   Action
WP-001 Contracts     codex     claude fallback   failed   high   [View]
WP-002 UI Shell      claude    claude            done     med    [View]
```

구현 컴포넌트:

- `ExecutionMatrixScreen`
  - header
  - `ExecutionPackageList`
  - execution log
- `ExecutionPackageRow`
  - `Static` columns
  - `Button("View", id=f"view-wp-{safe_id}")`
- `WorkPackageDetailModal`
  - WP 상세 설계 표시

대안:

`DataTable`을 유지하고 `Action` 컬럼에 `[View]` 텍스트를 넣은 뒤 `DataTable.CellSelected`를
처리할 수 있다. 구현량은 작지만 실제 버튼은 아니다. 이번 요구에는 실제 버튼 방식이 더 적합하다.

### WorkPackageSnapshot 확장

현재 snapshot은 execution table에 필요한 최소 정보만 갖고 있다.

추가 필드:

```python
objective: str = ""
scope: tuple[str, ...] = ()
out_of_scope: tuple[str, ...] = ()
dependencies: tuple[str, ...] = ()
expected_files: tuple[str, ...] = ()
acceptance_criteria: tuple[str, ...] = ()
requires_execution: bool = True
estimated_weight: int = 1
parallel_group: int | None = None
parallelizable: bool = True
repair_notes: tuple[str, ...] = ()
last_result_summary: str = ""
last_result_status: str = ""
last_result_files_changed: tuple[str, ...] = ()
last_result_blockers: tuple[str, ...] = ()
last_raw_response_path: str = ""
retryable: bool = False
retry_disabled_reason: str = ""
topic: str = ""
```

`retryable`은 UI에서 retry 대상 여부를 표시하는 데 사용한다.

### Detail modal 내용

`WorkPackageDetailModal`은 다음을 보여준다.

```text
WP-001 Contracts

Status: failed
Owner: codex
Current executor: -
Last executor: claude (fallback)
Retryable: yes

Objective
...

Scope
- ...

Out of scope
- ...

Dependencies
- WP-000

Expected files
- src/contracts.py

Acceptance criteria
- ...

Last execution result
Status: failed
Summary: ...
Files changed: ...
Blockers: ...
Raw artifact: /...

Repair notes
- ...
```

버튼:

- `Close`
- 선택 기능: `Retry this WP`

`Retry this WP`는 이번 범위에 포함할지 결정이 필요하다. 최소 범위는 "상세 보기" 버튼만이다.
하지만 `/execute-retry WP-001`와 자연스럽게 연결되므로, 다음 단계 구현에서는 modal 하단에
`Retry this WP` 버튼까지 넣는 것이 사용자 경험상 좋다.

권장 범위:

1차 구현:

- row별 `View` 버튼
- detail modal
- modal 안에 retry command hint 표시

2차 구현:

- `Retry this WP` 버튼
- 버튼 클릭 시 `confirm_execution_retry("custom", ["WP-001"])`

### Execution page event flow

```text
User clicks View
  -> ExecutionPackageRow posts WorkPackageDetailRequested(package_id)
  -> ExecutionMatrixScreen finds package snapshot
  -> push WorkPackageDetailModal(package)
```

`ExecutionMatrixScreen`은 snapshot-only screen이므로 workflow mutation은 하지 않는다.
retry 버튼을 2차 범위로 넣는다면 screen이 `RetryPackageRequested(package_id)` message를
app으로 post하고, app이 controller를 호출해야 한다.

## Report/status 반영

`/status`, `/workflow`, `/report`는 retryable package count를 표시한다.

예:

```text
Retryable packages: WP-001 failed, WP-003 blocked
Next: /execute-retry or /execute-retry WP-001
```

report export에는 retry event history를 포함한다.

## 테스트 계획

### Workflow engine

- failed workflow에서 `/execute-retry` plan이 failed WP를 선택한다.
- needs_user_decision workflow에서 blocked WP를 선택한다.
- done/needs_review WP는 skip된다.
- explicit WP id retry가 지정한 WP만 pending으로 되돌린다.
- skipped reason이 event에 기록된다.

### Textual controller

- `preview_execution_retry("all")`이 retry modal 목록을 만든다.
- `confirm_execution_retry("all")`이 failed/blocked/interrupted WP를 실행 시작한다.
- target workspace가 없으면 preflight required outcome을 반환한다.
- `confirm_execution_retry("custom", ["WP-001"])`가 지정 WP만 retry한다.
- active worker가 있으면 retry를 거부한다.

### Textual modal

- `/execute-retry` 입력 시 중앙 modal이 열린다.
- modal filter는 all/failed/blocked/interrupted/custom을 제공한다.
- custom 선택 시 WP row 옆에 체크박스가 같은 modal 안에서 나타난다.
- custom 해제 후 다른 filter를 누르면 체크박스가 사라지고 자동 선택 결과가 갱신된다.
- done/needs_review row는 disabled checkbox로 표시된다.
- 선택 가능한 WP가 없으면 `Retry selected` 버튼이 disabled 된다.

### Plain TUI

- `/execute-retry`가 retry plan을 출력한다.
- `/execute-retry failed`가 failed WP만 선택한다.
- `/execute-retry WP-999`가 no matching package 안내를 출력한다.

### Execution page

- row마다 `View` 버튼이 렌더링된다.
- 버튼 클릭 시 `WorkPackageDetailModal`이 열린다.
- modal에 objective/scope/expected files/acceptance criteria/result blockers가 표시된다.
- fallback executor는 owner와 분리되어 표시된다.

### Snapshot/report

- `WorkPackageSnapshot`이 상세 설계 필드를 projection한다.
- retryable flag와 disabled reason이 status 기준으로 계산된다.
- report에 retry event가 포함된다.

## 구현 순서

1. `/execute-retry` slash command 등록
2. `ExecutionRetryPlan`, `RetrySkip` model 추가
3. `WorkflowEngine.build_execution_retry_plan()` 추가
4. `WorkflowEngine.prepare_execution_retry()` 추가
5. 기존 `retry_interrupted_execution()`을 wrapper로 변경
6. Textual controller preview/confirm API 추가
7. `ExecuteRetryModal` 추가
8. Plain TUI `_cmd_execute_retry()` 추가
9. `WorkPackageSnapshot` 상세 필드 확장
10. `ExecutionMatrixScreen`을 row widget 기반으로 개편
11. `WorkPackageDetailModal` 추가
12. tests 추가
13. docs/test-results에 구현 결과 기록

## 리스크와 보완

| 리스크 | 보완 |
| :--- | :--- |
| partial output을 덮어쓸 수 있음 | retry plan에 target workspace와 previous raw artifact를 표시 |
| done WP 재실행 사고 | 기본 retry에서 done/needs_review 제외, skip reason 표시 |
| custom 선택 UX가 깊어질 수 있음 | 같은 modal 안에서 체크박스를 토글하고 depth를 만들지 않음 |
| DataTable에서 실제 버튼 구현 어려움 | row widget list로 전환 |
| retry 후 이전 execution result가 덮여 보일 수 있음 | event log/raw artifact는 보존하고, detail modal에 last result 중심으로 표시 |
| failed workflow state 전환 혼란 | retry 준비 시 state를 `blueprint_ready`, 실제 시작 시 `executing`으로 명확히 전환 |

## 완료 기준

- `/execute-retry`가 중앙 modal을 열고 retry plan을 보여준다.
- modal에서 all/failed/blocked/interrupted/custom을 선택할 수 있다.
- custom filter에서 WP row 옆 체크박스로 직접 선택할 수 있다.
- `/execute-retry`가 interrupted/failed/blocked WP를 명확히 재시작한다.
- `/execute-retry WP-ID`로 특정 WP만 재시작할 수 있다.
- done/needs_review WP는 기본 retry에서 제외된다.
- execution 페이지 각 WP row에 `View` 버튼이 있다.
- `View` 버튼으로 WP 상세 설계와 마지막 실행 결과를 볼 수 있다.
- Textual과 Plain TUI 모두 같은 retry selection 정책을 사용한다.
- 전체 관련 tests와 `git diff --check`가 통과한다.
