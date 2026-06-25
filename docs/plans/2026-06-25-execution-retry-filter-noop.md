# Execution Retry Filter No-op

## 배경

ExecutionRetryModal은 filter 버튼을 누를 때마다 selector를 다시 설정하고 `refresh(recompose=True)`를 호출한다. 사용자가 현재 선택된 filter를 다시 누르는 경우에는 표시할 package 목록과 selection 상태가 바뀌지 않지만, 기존 구현은 전체 modal recompose를 수행할 수 있었다.

## 개선 방향

- filter 버튼 클릭 시 다음 selector를 먼저 계산한다.
- 다음 selector가 현재 selector와 같으면 event만 소비하고 바로 반환한다.
- selector가 실제로 바뀌는 경우에는 기존처럼 selected_ids를 재계산하고 recompose한다.

## 범위

- `src/trinity/textual_app/widgets/execution_retry_modal.py`
- `tests/test_execution_retry_modal.py`

## 검증

- 현재 filter 버튼을 다시 누를 때 `refresh(recompose=True)`가 호출되지 않는지 확인한다.
- 다른 filter 버튼을 누르면 기존처럼 recompose가 호출되는지 확인한다.
- ExecutionRetryModal focused test와 전체 테스트를 통과시킨다.
