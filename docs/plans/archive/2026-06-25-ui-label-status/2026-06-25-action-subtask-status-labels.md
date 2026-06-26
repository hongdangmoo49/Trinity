# Action/Subtask presenter 상태값 지역화

## 배경

Nexus 중앙 뷰와 리포트는 한국어 UI에서 상태값을 공용 helper로 표시한다. 하지만 `/subtasks`와 `/improve` presenter는 아직 `done`, `waiting`, `pending` 같은 raw 상태값을 한국어 문장 안에 그대로 출력한다.

## 목표

- `/subtasks` markdown/table의 하위 작업 상태값을 한국어 표시값으로 렌더링한다.
- `/improve` table의 후속 조치 상태값을 한국어 표시값으로 렌더링한다.
- 영어 UI는 기존 raw 상태 표시를 유지한다.

## 작업 범위

1. `subtasks_markdown()`과 `subtasks_rows()`에서 `display_status_value()` helper를 사용한다.
2. `improve_rows()`에서 post-review action item 상태값을 helper로 표시한다.
3. post-review action 상태에 필요한 `proposed`, `accepted`, `ignored` 한국어 label을 추가한다.
4. 관련 presenter 테스트 기대값을 갱신한다.
5. 패치 버전을 `1.0.129`로 올린다.

## 검증 계획

- `uv run python -m py_compile src/trinity/textual_app/presenters.py src/trinity/textual_app/widgets/status_label.py tests/test_textual_app.py`
- `uv run pytest tests/test_textual_app.py -k "subtasks_presenter_uses_korean_labels or improve_presenter_uses_korean_labels" -q`
- `uv run pytest tests/test_textual_app.py -q`
- `uv run pytest -q`
