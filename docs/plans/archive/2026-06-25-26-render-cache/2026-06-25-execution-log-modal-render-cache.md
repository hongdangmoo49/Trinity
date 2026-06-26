# Execution Log Modal Render State Cache

## 배경

ExecutionLogModal은 검색어가 바뀔 때마다 status text와 visible log lines를 계산한 뒤, 같은 결과여도 status label update와 `RichLog.clear()`/write를 반복한다. 입력값은 `strip()` 처리되므로 같은 검색 상태가 다시 refresh될 수 있고, 이때 렌더 결과가 동일하면 화면 갱신은 불필요하다.

## 개선 방향

- 마지막 status text와 visible rendered lines를 캐시한다.
- `_refresh_log()`에서 status text와 rendered lines가 모두 같으면 바로 반환한다.
- status만 바뀐 경우 status label만 갱신하고, lines만 바뀐 경우 log body만 갱신한다.

## 범위

- `src/trinity/textual_app/widgets/execution_log_modal.py`
- `tests/test_execution_log_modal_cache.py`

## 검증

- 같은 검색 상태를 다시 refresh할 때 status update, clear, write가 모두 생략되는지 확인한다.
- 로그 모달 관련 focused test와 전체 테스트를 통과시킨다.
