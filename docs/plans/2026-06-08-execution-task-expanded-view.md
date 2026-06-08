# Execution Task Expanded View

작성일: 2026-06-08

브랜치: `codex/execution-task-expanded-view`

상태: 1차 구현 반영

## 배경

Execution Matrix의 task 목록은 현재 고정 폭/고정 높이로 렌더링된다. task title은
28자 기준으로 잘리고, 목록 영역도 11줄로 제한되어 WP 수가 많거나 제목이 긴 경우
사용자가 현재 어떤 작업이 돌고 있는지 빠르게 확인하기 어렵다.

`Spec` 버튼은 개별 WP의 상세 설계를 확인하는 데 유용하지만, 전체 execution task 목록을
한눈에 넓게 보는 용도와는 다르다.

## 목표

Execution 페이지에서 task 영역을 즉시 크게 볼 수 있는 UI를 제공한다.

- Execution Matrix 안에서 task 목록 영역을 확장/축소한다.
- 확장 상태에서는 task 컬럼을 더 넓게 보여주고, package list가 화면 대부분을 사용한다.
- 축소 상태에서는 기존처럼 execution log가 더 넓은 공간을 차지한다.
- 사용자는 키보드와 버튼 양쪽으로 전환할 수 있다.
- 실행 상태, log, package row, `Spec` modal 동작은 유지한다.

## 비목표

- 별도 전체 화면 route를 추가하지 않는다.
- WP 상세 modal을 대체하지 않는다.
- execution log를 숨기거나 삭제하지 않는다.
- terminal 외부 창, 마우스 전용 UX, 새 persistence 항목은 추가하지 않는다.

## UX 계약

### 기본 모드

- 기존 Execution Matrix와 동일하게 표시한다.
- task title은 좁은 컬럼에 맞춰 줄인다.
- log 영역은 `1fr`로 남아 실행 로그를 계속 볼 수 있다.

### 확장 모드

- `f` 키 또는 `Expand Tasks` 버튼을 누르면 확장 모드가 된다.
- package list는 `1fr` 높이로 커진다.
- execution log는 하단의 작은 영역으로 줄어든다.
- task 컬럼은 더 긴 문자열을 표시한다.
- 버튼 label은 `Compact Tasks`로 바뀐다.
- 같은 키/버튼을 다시 누르면 기본 모드로 돌아간다.

### 접근성/운영성

- 키보드 조작이 가능해야 한다.
- 현재 화면에서만 유지되는 UI state로 충분하다. resume/session persistence에 저장하지 않는다.
- 긴 task title은 layout을 깨지 않도록 여전히 안전하게 clip한다.

## 구현 계획

1. `ExecutionMatrixScreen`에 `tasks_expanded` 상태를 추가한다.
2. 화면 상단을 header + toggle button row로 바꾼다.
3. `Binding("f", "toggle_task_expanded", "Expand Tasks")`를 추가한다.
4. package row 렌더링 시 expanded 여부에 따라 task clip width를 다르게 적용한다.
5. CSS class `execution-task-expanded`로 package list/log 높이와 task 컬럼 폭을 조정한다.
6. Textual 테스트로 버튼/키 토글과 기존 row 동작을 검증한다.

## 테스트 기준

- 기본 렌더링에서 기존 package row가 유지된다.
- `f` 키 또는 toggle button으로 expanded class가 켜진다.
- expanded 상태에서 긴 task title이 더 길게 표시된다.
- 두 번째 토글로 compact 상태가 복원된다.
- 기존 `Spec` 버튼 modal 동작이 깨지지 않는다.

## 1차 구현 결과

- `ExecutionMatrixScreen`에 `tasks_expanded` UI 상태를 추가했다.
- `f` 키 바인딩과 `Expand Tasks`/`Compact Tasks` 토글 버튼을 추가했다.
- 확장 상태에서는 `#execution-screen`에 `execution-task-expanded` class를 적용한다.
- CSS에서 확장 상태의 package list를 `1fr`, execution log를 `8` 높이로 조정한다.
- compact 상태 task clip width는 기존과 같은 `28`, expanded 상태는 `72`로 늘렸다.
- 기존 `Spec` 버튼과 WP detail modal 동작은 유지했다.

## 검증

```text
uv run pytest tests/test_textual_app.py::test_execution_matrix_expands_task_area tests/test_textual_app.py::test_execution_matrix_separates_owner_and_executor tests/test_textual_app.py::test_execution_matrix_renders_preflight_and_packages -q
```

결과:

```text
3 passed in 2.29s
```

추가 확인:

```text
uv run python -m py_compile src/trinity/textual_app/screens/execution_matrix.py
```

결과: 통과.
