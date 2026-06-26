# QuestionPanel 상태 토큰 지역화

## 배경

Nexus 질문 패널은 제목, 빈 상태, 답변 라벨은 한국어로 표시하지만 질문 행의 상태 토큰은 `[open]`, `[answered]`처럼 영어 원문으로 렌더링된다. 한국어 UI에서 질문 패널은 사용자가 직접 결정을 내리는 영역이므로 상태 표시도 일관되게 지역화하는 편이 자연스럽다.

## 목표

- 한국어 UI에서 질문 상태 토큰을 `열림`, `답변됨`으로 표시한다.
- 영어 UI의 기존 `open`, `answered` 표시는 유지한다.
- 미등록 상태값은 디버깅 가능성을 위해 원문 그대로 보존한다.

## 작업 범위

1. `QuestionPanel`에 상태값 표시 헬퍼를 추가한다.
2. 질문 행 렌더링에서 원시 상태값 대신 표시 상태값을 사용한다.
3. 한국어 질문 패널에서 열린 질문과 답변된 질문이 지역화되는 회귀 테스트를 추가한다.

## 검증 계획

- `uv run python -m py_compile src/trinity/textual_app/widgets/question_panel.py tests/test_textual_app.py`
- `uv run pytest tests/test_textual_app.py -k "central_agent_view_renders_all_questions or question_panel_localizes" -q`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest -q`
