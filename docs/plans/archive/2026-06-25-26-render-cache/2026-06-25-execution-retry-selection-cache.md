# Execution Retry Selection State Cache

## 배경

ExecutionRetryModal은 custom checkbox 변경 시 선택된 WP 목록 문구와 confirm 버튼 disabled 상태를 갱신한다. 선택 상태가 실제로 바뀌지 않은 refresh에서도 같은 텍스트 update와 disabled 대입이 반복될 수 있다.

실행 페이지 주변 모달들도 중복 렌더를 줄이는 방향으로 정리하고 있으므로, retry modal 선택 상태도 동일한 캐시 패턴을 적용한다.

## 개선 방향

- 마지막 selected text와 confirm disabled 상태를 저장한다.
- `_refresh_selection_state()`는 selected text가 바뀐 경우에만 label을 update한다.
- confirm disabled 값이 바뀐 경우에만 버튼 상태를 대입한다.

## 범위

- `src/trinity/textual_app/widgets/execution_retry_modal.py`
- `tests/test_execution_retry_modal.py`

## 검증

- 선택 상태가 그대로일 때 selected label update가 생략되는지 확인한다.
- 선택 상태가 비면 selected label과 confirm disabled가 정상 갱신되는지 확인한다.
- Retry modal focused test와 전체 테스트를 통과시킨다.
