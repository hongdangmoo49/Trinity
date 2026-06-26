# Questions/Inspector 상태값 지역화

## 배경

QuestionPanel은 한국어 UI에서 `열림`, `답변됨`을 표시하지만 `/questions` presenter는 아직 `open`, `answered`를 그대로 노출한다. 또한 Workflow Inspector의 post-review 항목은 `high/pending`처럼 raw 상태를 표시한다.

## 목표

- `/questions` markdown/table에서 질문 상태를 한국어 표시값으로 렌더링한다.
- Workflow Inspector의 post-review 상태를 한국어 표시값으로 렌더링한다.
- 영어 UI는 기존 raw 상태 표시를 유지한다.

## 작업 범위

1. presenter에 질문 상태 표시 helper를 추가한다.
2. `questions_markdown()`과 `questions_rows()`에서 질문 상태를 지역화한다.
3. Inspector post-review item 상태에 `display_status_value()`를 적용한다.
4. 관련 테스트 기대값을 갱신한다.
5. 패치 버전을 `1.0.131`로 올린다.

## 검증 계획

- `uv run python -m py_compile src/trinity/textual_app/presenters.py src/trinity/textual_app/widgets/inspector.py tests/test_textual_app.py`
- `uv run pytest tests/test_textual_app.py -k "questions_presenter_uses_korean_labels or inspector" -q`
- `uv run pytest tests/test_textual_app.py -q`
- `uv run pytest -q`
