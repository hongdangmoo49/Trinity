# Execution Matrix State Identity Cache

## 배경

ExecutionMatrixScreen은 route refresh나 workflow outcome 적용 시 `apply_execution_state()`에서 chrome, task list, activity log 렌더 경로를 순서대로 호출한다. 각 하위 렌더러에도 render key cache가 있지만, 같은 preflight/snapshot 객체 조합이 다시 적용되는 경우에는 상위 화면에서 전체 적용을 생략할 수 있다.

## 개선 방향

- ExecutionMatrixScreen이 마지막으로 적용한 `(preflight identity, snapshot identity)`를 저장한다.
- mounted 상태에서 같은 identity 조합이 다시 들어오면 `self.preflight`와 `self.snapshot`만 유지하고 바로 반환한다.
- `append_log()`처럼 snapshot 밖에서 화면 log를 직접 바꾸는 경로는 identity cache를 무효화한다.
- 같은 내용의 새 snapshot 객체는 기존처럼 렌더 경로를 통과한다.

## 범위

- `src/trinity/textual_app/screens/execution_matrix.py`
- `tests/test_execution_matrix_state_cache.py`

## 검증

- 같은 preflight/snapshot 객체 조합을 다시 적용할 때 chrome/package/log render가 호출되지 않는지 확인한다.
- 같은 내용의 새 snapshot 객체는 기존처럼 render 경로를 통과하는지 확인한다.
- direct log append 후 같은 snapshot을 다시 적용하면 log render가 다시 호출되는지 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
