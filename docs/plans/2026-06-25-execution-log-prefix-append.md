# Execution Activity Log Prefix Append

## 배경

실행 페이지의 activity log는 표시 라인이 바뀌면 `RichLog.clear()` 후 모든 activity line을 다시 write한다. 실행 로그는 짧은 구간에서는 주로 뒤에 새 라인이 append되는 형태라, 기존 표시 라인을 유지한 채 새 라인만 추가할 수 있다.

다만 최근 7줄 window가 밀리거나 숨김 카운트가 바뀌는 경우에는 기존 라인의 내용도 달라진다. 이 경우는 전체 재렌더가 맞다.

## 개선 방향

- `_render_log()`에서 새 activity lines가 기존 key를 prefix로 포함하는지 확인한다.
- prefix append인 경우 `RichLog.clear()` 없이 새 라인만 write한다.
- prefix가 아니면 기존처럼 clear 후 전체 라인을 다시 write한다.

## 범위

- `src/trinity/textual_app/screens/execution_matrix.py`
- `tests/test_execution_activity_log.py`

## 검증

- 짧은 로그에 새 라인이 추가되는 경우 clear 없이 새 라인만 write되는지 확인한다.
- recent window가 바뀌는 경우 clear 경로가 유지되는지 확인한다.
- 실행 페이지 관련 focused test와 전체 테스트를 통과시킨다.
