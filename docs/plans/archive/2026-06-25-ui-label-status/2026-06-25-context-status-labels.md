# Context markdown 상태값 지역화

## 배경

`/context`와 Nexus context markdown은 현재 워크플로우를 사용자와 에이전트가 같이 읽는 요약이다. 최근 presenter와 report 화면의 상태값은 한국어 표시값으로 정리했지만, context markdown의 subtask와 post-review action item 상태는 아직 `[waiting]`, `[pending]` 같은 raw 값으로 남아 있다.

## 목표

- 한국어 context markdown의 subtask 상태값을 `대기`, `완료`처럼 표시한다.
- 한국어 context markdown의 post-review action item 상태값을 `대기`, `완료`처럼 표시한다.
- 영어 UI는 기존 raw 상태 표시를 유지한다.

## 작업 범위

1. `snapshot_context_markdown()`의 subtask 상태에 `_status_value()`를 적용한다.
2. `snapshot_context_markdown()`의 post-review action item 상태에 `_status_value()`를 적용한다.
3. 기존 context presenter 테스트 기대값을 갱신한다.
4. 패치 버전을 `1.0.130`으로 올린다.

## 검증 계획

- `uv run python -m py_compile src/trinity/textual_app/presenters.py tests/test_textual_app.py`
- `uv run pytest tests/test_textual_app.py -k "context_presenter_uses_korean_labels or central_agent_view_localizes_korean_status_values" -q`
- `uv run pytest tests/test_textual_app.py -q`
- `uv run pytest -q`
