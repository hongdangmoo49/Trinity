# Execution Task Expanded Cache

## 배경

ExecutionMatrixScreen은 작업 목록을 compact/expanded 상태로 전환할 때
`#execution-screen`에 `execution-task-expanded` 클래스를 동기화한다. 화면 mount,
execution state 적용, 토글 액션 경로가 같은 동기화 함수를 공유하기 때문에 이미 같은
상태가 반영된 뒤에도 widget query와 `set_class()` 호출이 반복될 수 있다.

최근 Nexus 실행 페이지 최적화는 동일 projection이나 동일 입력을 다시 그리지 않는
방향으로 정리되고 있다. 작업 확장 클래스도 같은 정책으로 맞추면 WP 완료 직후처럼
화면 갱신이 잦은 구간에서 불필요한 class mutation을 줄일 수 있다.

## 개선 방향

- ExecutionMatrixScreen에 마지막으로 반영한 task expanded 상태를 캐시한다.
- `_sync_task_expanded_view()`는 mounted 상태에서 현재 값이 캐시와 같으면 바로 반환한다.
- 값이 바뀐 경우에만 `#execution-screen`을 조회하고 `set_class()`를 호출한다.

## 범위

- `src/trinity/textual_app/screens/execution_matrix.py`
- `tests/test_execution_matrix_state_cache.py`

## 검증

- 같은 task expanded 상태를 다시 동기화할 때 class sync가 발생하지 않는지 확인한다.
- task expanded 상태가 바뀌면 기존처럼 class가 한 번 반영되는지 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
