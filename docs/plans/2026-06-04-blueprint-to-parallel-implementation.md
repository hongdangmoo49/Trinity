# Blueprint Ready -> Parallel Implementation 전환 설계

작성일: 2026-06-04
상태: 설계/정책 문서
관련 코드:

- `src/trinity/workflow/models.py`
- `src/trinity/workflow/engine.py`
- `src/trinity/workflow/execution.py`
- `src/trinity/providers/policy.py`
- `src/trinity/tui/session.py`

---

## 1. 목적

이 문서는 Trinity가 설계 단계에서 만든 `blueprint_ready` 산출물을 실제 구현 단계로 자연스럽게 넘기는 방식을 정의한다.

핵심 목표는 다음과 같다.

```text
설계도(blueprint)를 하나의 빵으로 보고,
동시에 먹을 수 있는 독립 조각(work package)을 찾아,
활성 에이전트 수만큼 균형 있게 나누어,
각 에이전트가 격리된 작업공간에서 병렬 구현한다.
```

이 방식에서 provider 우선순위는 작업 분배의 중심 규칙이 아니다. 중심 규칙은 독립성, 충돌 가능성, 작업량 균형, provider 적합도다. `codex -> claude -> antigravity` 같은 provider 우선순위는 동률 처리, fallback, 단일 담당자 선택에만 사용한다.

---

## 2. 현재 기준점

최신 workflow 모델에는 이미 다음 상태와 자료구조가 있다.

```text
WorkflowState:
  idle
  preflight
  deliberating
  needs_user_decision
  blueprint_ready
  executing
  reviewing
  done
  failed
```

`WorkflowSession`은 `blueprint`, `work_packages`, `execution_results`, `decisions`를 보존한다. `WorkPackage`는 다음 실행 스케줄링 정보도 가진다.

```text
id
title
owner_agent
objective
scope
out_of_scope
dependencies
expected_files
acceptance_criteria
status
requires_execution
```

현재 TUI에는 `blueprint_ready` 상태에서 `/execute`를 호출해 현재 blueprint의 work package를 executable로 재생성하고 실행하는 흐름이 있다. `ExecutionProtocol`은 dependency-ready package를 고르고 `ParallelExecutionPolicy`로 병렬 batch를 만든 뒤 `asyncio.gather()`로 실행한다.

따라서 이 문서의 설계는 완전히 새 엔진을 만들자는 뜻이 아니라, 현재 구조를 사용자가 기대하는 "설계 -> 승인 -> 병렬 구현 -> 병합/검증" 흐름으로 명확히 고정하는 정책이다.

---

## 3. 사용자 경험 계약

`blueprint_ready`는 설계 완료 상태다. 이 상태에 진입하는 것만으로 파일을 수정하면 안 된다.

설계가 끝나면 TUI는 다음처럼 표시한다.

```text
Blueprint ready

Work packages: 7
Parallel groups: 3
Active providers: codex, claude, antigravity

Next action
> Implement all packages
  Select packages
  Revise blueprint
  Stop here
```

사용자가 다음 의도를 표현하면 구현 단계로 넘어간다.

```text
/execute
개발해라
구현해라
진행해라
이대로 만들어라
```

반대로 다음 의도는 구현으로 넘어가지 않는다.

```text
설계만 해라
구현하지 마라
파일을 바꾸지 마라
대안을 더 검토해라
```

애매한 입력은 기존 blueprint를 폐기하고 새 토론을 시작하지 않는다. 먼저 사용자에게 다음 선택지를 보여준다.

```text
현재 설계도가 준비되어 있습니다.

> 이 설계도로 구현 시작
  이 설계를 더 다듬기
  새 요청으로 시작
  취소
```

---

## 4. 상태 전환

외부에 노출되는 persisted state는 현재 enum을 우선 사용한다.

```text
deliberating
  -> needs_user_decision
  -> deliberating
  -> blueprint_ready
  -> executing
  -> reviewing
  -> done
```

구현 승인 직후의 내부 절차는 다음과 같이 해석한다.

```text
blueprint_ready
  -> implementation_requested
  -> planning_execution
  -> executing_batches
  -> integrating
  -> validating
  -> reviewing
  -> done
```

`implementation_requested`, `planning_execution`, `executing_batches`, `integrating`, `validating`은 당장 `WorkflowState`에 추가하지 않아도 된다. 초기에는 event log와 TUI status label로 표현하고, 재개/중단 복구에 필요해지면 별도 enum으로 승격한다.

---

## 5. Blueprint 불변성

구현 요청이 들어오면 원본 blueprint는 immutable artifact로 고정한다.

원칙:

- `blueprint_ready` 이후 구현 중에는 원본 blueprint를 수정하지 않는다.
- 구현 중 새 결정이 필요하면 `DecisionRecord`로 추가한다.
- 새 결정이 blueprint의 전제를 바꾸면 실행을 멈추고 `needs_user_decision` 또는 `deliberating`으로 되돌린다.
- 실행 결과는 `ExecutionResult`와 ledger에 기록하고, 원본 설계와 실제 구현 차이를 추적한다.

권장 artifact:

```text
.trinity/workflow/session.json
.trinity/workflow/events.jsonl
.trinity/workflow/blueprints/<blueprint_id>.json
.trinity/workflow/runs/<run_id>/...
```

---

## 6. Work Package 분해 정책

`work_packages`는 provider 수에 맞춰 기계적으로 먼저 3개를 만드는 것이 아니다. 먼저 설계도를 독립 deliverable 단위로 쪼갠다.

좋은 package 조건:

- 하나의 명확한 objective를 가진다.
- acceptance criteria가 독립적으로 검증 가능하다.
- 예상 수정 파일이 `expected_files`에 들어 있다.
- 다른 package가 먼저 끝나야 하면 `dependencies`에 package id를 넣는다.
- 같은 파일을 동시에 수정할 가능성이 있으면 같은 batch에 넣지 않는다.

예시:

```text
WP-001 config schema 추가
  expected_files: src/trinity/config.py, tests/test_config.py

WP-002 execution scheduler 추가
  expected_files: src/trinity/workflow/execution.py, tests/test_execution_protocol.py

WP-003 TUI 실행 선택지 추가
  dependencies: WP-002
  expected_files: src/trinity/tui/session.py, tests/test_tui_session.py

WP-004 docs 갱신
  expected_files: docs/
```

---

## 7. 병렬 그룹화 정책

병렬 실행은 dependency graph와 file ownership을 모두 통과한 package에만 허용한다.

절차:

```text
1. 전체 work_packages를 DAG로 해석한다.
2. 아직 완료되지 않은 package 중 dependencies가 모두 DONE인 ready set을 만든다.
3. expected_files가 겹치는 package를 같은 batch에서 제외한다.
4. 같은 worktree에서 provider-managed write가 두 개 이상이면 직렬화한다.
5. 별도 git worktree를 쓰고 병합을 순차 처리할 수 있으면 병렬 실행을 허용한다.
6. batch가 끝나면 결과를 기록하고 다음 ready set을 계산한다.
```

현재 `ParallelExecutionPolicy`는 다음 보수적 규칙을 이미 제공한다.

- read-only invocation은 병렬 허용
- provider-managed workspace-write가 같은 workspace를 공유하면 기본 직렬화
- file ownership이 명시적으로 disjoint하면 병렬 허용
- workspace가 분리되어 있으면 병렬 허용

이 정책은 유지하되, 실제 구현 실행에서는 provider별 isolated worktree를 기본값으로 삼는다.

---

## 8. Provider 할당 정책

provider 우선순위는 "어려운 작업을 codex부터 준다"는 뜻이 아니다.

할당 우선순위:

```text
1. dependencies가 풀린 package인가?
2. 같은 batch에서 파일 충돌이 없는가?
3. 활성 provider 수에 맞게 작업량이 균형 잡히는가?
4. package 성격과 provider/agent role이 맞는가?
5. 완전히 동률이면 provider priority를 tie-breaker로 사용한다.
```

provider priority의 용도:

- 활성 provider가 일부뿐일 때 기본 후보 순서 결정
- 같은 package에 같은 점수의 provider가 여러 개일 때 tie-break
- synthesis, review coordinator, merge coordinator 같은 단일 담당자 선택
- provider 실패 시 fallback 순서 결정

기본 priority:

```text
codex -> claude -> antigravity
```

이 priority는 작업 난이도 순서가 아니다. 작업 난이도는 package의 risk/complexity score와 acceptance criteria로 따로 계산해야 한다.

---

## 9. 실행 공간과 병합

각 provider는 같은 working tree를 동시에 직접 수정하지 않는다.

권장 구조:

```text
.trinity/workspace/runs/<run_id>/codex/
.trinity/workspace/runs/<run_id>/claude/
.trinity/workspace/runs/<run_id>/antigravity/
```

실행 흐름:

```text
1. run_id를 만든다.
2. provider별 git worktree를 만든다.
3. 각 package prompt에는 blueprint id, package id, scope, expected_files, acceptance criteria를 넣는다.
4. provider는 자기 worktree에서만 파일을 수정한다.
5. 각 package 완료 후 diff, files_changed, test result를 수집한다.
6. orchestrator가 integration branch에 순차 병합한다.
7. 충돌이 나면 resolve package를 만들거나 사용자 결정으로 전환한다.
8. 전체 검증 후 review 단계로 넘긴다.
```

병합은 항상 중앙 orchestrator가 수행한다. provider가 직접 main branch나 integration branch를 push하지 않는다.

---

## 10. 검증과 커밋 단위

검증은 package 단위와 전체 통합 단위로 나눈다.

package 단위:

- package acceptance criteria 확인
- package 관련 targeted tests 실행
- provider가 보고한 `files_changed`와 실제 diff 비교

통합 단위:

- 전체 lint/test 실행
- workflow ledger와 execution results 갱신
- docs/test-results 작성
- checkpoint 또는 plan 문서 갱신

커밋 정책:

- 가능하면 독립 package 단위로 commit한다.
- 같은 batch의 package들이 서로 강하게 엮여 있으면 batch 단위 commit을 허용한다.
- 충돌 해결 commit은 별도 commit으로 남긴다.
- 최종 검증/문서 갱신 commit은 필요하면 별도로 둔다.

---

## 11. TUI/CLI 동작 예시

### 설계만 요청

```text
User:
  L2 브릿지 경로 파인더를 설계해줘

Trinity:
  deliberating -> needs_user_decision -> blueprint_ready
  "Blueprint ready. Implement, revise, or stop?"
```

파일 변경 없음.

### 이후 구현 요청

```text
User:
  개발해라

Trinity:
  현재 blueprint를 executable work packages로 재생성
  dependency/file ownership 기반 batch 생성
  provider별 isolated worktree 실행
  병합/검증/review
```

### 명시적 명령

```text
/execute 비용 최저 경로를 우선 구현해라
```

`DecisionRecord`에 사용자 실행 지시를 남기고 구현으로 넘어간다.

---

## 12. 수용 기준

이 설계가 완료된 것으로 보려면 다음 조건을 만족해야 한다.

- `blueprint_ready` 진입만으로 파일이 수정되지 않는다.
- `blueprint_ready`에서 "개발해라" 또는 `/execute`가 기존 blueprint를 사용한다.
- 구현 요청이 새 deliberation을 시작하지 않는다.
- work package는 dependencies와 expected_files를 가진다.
- dependency가 풀리지 않은 package는 실행하지 않는다.
- 같은 workspace에서 충돌 가능성이 있는 provider-managed write는 병렬 실행하지 않는다.
- 별도 worktree와 disjoint file ownership이 있으면 병렬 실행한다.
- provider priority는 tie-break/fallback에만 사용한다.
- 실행 결과는 `ExecutionResult`와 workflow ledger에 기록된다.
- 모든 package가 done이면 review로 넘어간다.
- failed/blocked package는 `failed` 또는 `needs_user_decision` 상태로 반영된다.

---

## 13. 구현 후보 작업

이 문서를 코드로 반영할 때의 작업 단위는 다음과 같다.

```text
WP-A. Blueprint execution intent routing
  - "개발해라", "구현해라" 등 blueprint-ready text를 execute action으로 분류
  - ambiguous text는 선택 UI로 처리

WP-B. Work package scheduler hardening
  - dependency-ready set 계산 검증
  - package complexity/weight 계산
  - provider별 load balancing

WP-C. Isolated worktree execution
  - run_id별 provider worktree 생성
  - execution prompt에 workspace boundary 명시
  - diff/result 수집

WP-D. Integration and conflict handling
  - package result를 integration branch에 순차 병합
  - conflict 발생 시 resolve package 또는 user decision으로 전환

WP-E. Verification and commit workflow
  - package targeted tests
  - full test gate
  - package/batch 단위 commit 규칙 적용

WP-F. TUI display
  - blueprint_ready action picker
  - batch/package execution progress
  - blocked/failed package action picker
```

---

## 14. 설계 결정

최종 결정:

- 설계 완료와 구현 시작은 분리한다.
- 구현은 사용자 승인 이후에만 시작한다.
- work package 분배는 provider priority가 아니라 독립성/충돌/균형/적합도 중심으로 한다.
- provider priority는 tie-breaker와 fallback으로만 사용한다.
- 병렬 구현은 provider별 isolated worktree를 기본 전제로 한다.
- 병합, 검증, 커밋은 orchestrator가 중앙에서 순차적으로 관리한다.
