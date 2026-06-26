# Execution Log Query Input Cache

## 배경

ExecutionLogModal은 실행 로그 전체 보기에서 검색어가 바뀔 때 `_refresh_log()`를 호출한다. `_refresh_log()` 내부에는 status text와 rendered lines cache가 있어 같은 렌더 결과의 UI update는 생략한다.

하지만 같은 검색어가 다시 입력되는 경우에도 `_render_state()`와 필터 계산은 반복된다. 검색어를 trim한 값이 이미 적용된 `filter_query`와 같다면 입력 이벤트 단계에서 바로 no-op 처리할 수 있다.

## 개선 방향

- `on_input_changed()`에서 `event.value.strip()` 결과를 먼저 계산한다.
- normalized query가 현재 `filter_query`와 같으면 바로 반환한다.
- query가 달라진 경우에만 `self.filter_query`를 갱신하고 `_refresh_log()`를 호출한다.
- `_refresh_log()`의 기존 render state cache는 그대로 유지한다.

## 범위

- `src/trinity/textual_app/widgets/execution_log_modal.py`
- `tests/test_execution_log_modal_cache.py`

## 검증

- 같은 normalized 검색어가 다시 입력될 때 `_refresh_log()`가 호출되지 않는지 확인한다.
- 다른 검색어가 입력되면 기존처럼 `_refresh_log()`가 호출되고 `filter_query`가 갱신되는지 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
