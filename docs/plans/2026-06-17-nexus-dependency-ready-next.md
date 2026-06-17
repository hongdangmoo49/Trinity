# Nexus Dependency-Ready Next WP Design

작성일: 2026-06-17

브랜치: `feature/nexus-dependency-ready-next`

상태: 구현 예정

## 배경

직전 Nexus UI 작업에서 Inspector 상단에 `Progress`, `Current`, `Next`, `Blocked` 섹션을 추가했다.
하지만 현재 `Next`는 `pending`, `queued`, `waiting` 상태의 WP를 단순히 앞에서부터 보여준다. 실제
실행 엔진은 dependency가 모두 완료된 WP만 ready batch에 넣기 때문에, Nexus가 보여주는 `Next`와 실제
실행 가능한 WP가 어긋날 수 있다.

예를 들어 `WP-003`이 `pending`이어도 `WP-001`을 dependency로 갖고 있고 `WP-001`이 아직 running이면,
사용자에게는 `WP-003`이 다음 실행 대상처럼 보이지만 실제로는 기다리는 항목이다.

## 목표

1. Nexus Inspector의 `Next`가 dependency-ready WP를 먼저 보여주도록 한다.
2. dependency가 남은 waiting WP는 `waiting on WP-xxx` 형태로 이유를 표시한다.
3. 같은 parallel group에서 동시에 ready인 WP가 있으면 같은 그룹임을 드러낸다.
4. 중앙 Work Packages 요약과 기존 progress count는 장황해지지 않게 유지한다.
5. workflow engine, session 저장 포맷, WorkPackage schema는 변경하지 않는다.

## 비목표

- 실행 스케줄러의 정책을 변경하지 않는다.
- parallel policy의 파일 소유권 충돌 계산을 Textual projection에서 재구현하지 않는다.
- Inspector를 탭 구조로 재설계하지 않는다.
- Execution Matrix 전체 레이아웃을 바꾸지 않는다.

## 현재 구현 기준

`src/trinity/textual_app/widgets/progress_summary.py`의 `next_work_packages()`는 다음 조건만 본다.

- `work_package_state(package) == "waiting"`
- 입력 순서 기준 앞 `limit`개

`src/trinity/workflow/execution.py`의 실제 실행 흐름은 다음과 다르다.

- 현재 실행 대상 후보는 `requires_execution`이 true이고 완료/리뷰필요가 아닌 WP다.
- dependency 목록 중 같은 실행 후보에 있고 status가 `done`이 아닌 WP가 있으면 blocked dependency로 본다.
- blocked dependency가 없는 WP만 ready package가 된다.
- ready package들은 parallel policy에 따라 batch로 묶인다.

Textual snapshot의 `WorkPackageSnapshot`에는 이미 다음 필드가 있다.

- `id`
- `status`
- `dependencies`
- `parallel_group`
- `parallelizable`
- `requires_execution`

따라서 별도 persistence 없이 UI projection helper에서 충분히 계산할 수 있다.

## UX 계약

### Inspector Next

`Next`는 최대 3개의 ready WP를 먼저 보여준다.

```text
Next
- WP-002 Codex · Parser
- WP-004 Claude · Renderer · group 1
```

ready WP가 없고 dependency가 남은 waiting WP가 있으면 대기 이유를 보여준다.

```text
Next
- WP-003 Claude · Renderer
  waiting on WP-001
```

ready WP와 dependency-waiting WP가 섞이면 ready WP를 먼저 보여주고, 남은 공간에 waiting 이유를 보여준다.

```text
Next
- WP-002 Codex · Parser
- WP-003 Claude · Renderer
  waiting on WP-001
```

표시 개수를 넘는 ready/waiting 후보가 있으면 기존처럼 `+N more`를 유지한다.

### Central Area

중앙 `Work Packages` 요약은 기존 compact 계약을 유지한다.

- progress count
- current 1개
- blocked 1개
- 상세는 Inspector/Report 안내

`Next` 상세 이유는 중앙에 추가하지 않는다. 중앙은 여전히 판단과 다음 액션 중심이다.

## 구현 계획

### 1. Design Doc

- 이 문서를 추가한다.
- 구현 전 범위와 UX 계약을 고정한다.

### 2. Progress Helper 확장

`progress_summary.py`에 다음 pure helper를 추가한다.

- `blocked_dependency_ids(package, packages_by_id)`
- `next_work_package_entries(packages, limit=3)`
- `next_work_package_line(entry)`

entry는 다음 정보를 담는다.

- package
- waiting_on
- ready
- parallel_group

기존 `next_work_packages()`는 compatibility wrapper로 남겨 ready WP를 우선 반환하게 한다.

### 3. Inspector 렌더링 갱신

- `WorkflowInspector`의 `Next` 렌더링을 새 entry 기반으로 바꾼다.
- dependency waiting 항목에는 다음 줄에 `waiting on ...`을 붙인다.
- `+N more`는 entry 전체 후보 수 기준으로 계산한다.

### 4. 테스트

다음 회귀를 추가한다.

- dependency가 완료된 pending WP가 먼저 표시된다.
- dependency가 완료되지 않은 pending WP는 `waiting_on`을 가진다.
- ready WP가 dependency waiting WP보다 우선한다.
- 같은 parallel group의 ready WP line에 group 정보가 표시된다.
- Inspector Next가 waiting reason을 렌더한다.

## 검증 명령

현재 환경에서는 `uv`가 WSL PATH에 없을 수 있으므로 `.venv`를 우선 사용한다.

```text
/home/user/workspace/Trinity/.venv/bin/python -m pytest \
  /home/user/workspace/Trinity/tests/test_progress_summary.py \
  /home/user/workspace/Trinity/tests/test_textual_app.py \
  /home/user/workspace/Trinity/tests/test_central_agent_view.py \
  -q
```

필요하면 전체 Textual 회귀를 추가로 돌린다.

```text
/home/user/workspace/Trinity/.venv/bin/python -m pytest \
  /home/user/workspace/Trinity/tests/test_textual_snapshot.py \
  /home/user/workspace/Trinity/tests/test_textual_workflow_controller.py \
  /home/user/workspace/Trinity/tests/test_textual_smoke.py \
  -q
```

## 리스크

- UI projection은 execution engine의 parallel policy 전체를 재구현하지 않는다. 따라서 group 표시는 같은
  `parallel_group`인 ready WP를 함께 보여주는 힌트이며, 파일 소유권 충돌까지 보장하는 scheduler 결과는 아니다.
- dependency가 외부 문자열이거나 현재 snapshot에 없는 WP id이면 internal blocker로 보지 않는다. 이는 현재
  execution engine의 `_blocked_dependencies()`와 맞춘 의도적인 처리다.
- `Next`가 더 정확해지는 대신, 사용자가 `pending` WP를 전부 "곧 실행"으로 보던 기존 체감과 달라질 수 있다.
  waiting reason을 같이 보여 혼동을 줄인다.
