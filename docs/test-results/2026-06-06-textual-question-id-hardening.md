# Textual Question ID Hardening

작성일: 2026-06-06

브랜치: `codex/execution-matrix-hardening`

## 문제

사용자 decision 질문이 표시되는 순간 Textual 앱이 다음 예외로 중단됐다.

```text
BadIdentifier: 'answer-...-1' is an invalid id; identifiers must contain only letters, numbers, underscores, or hyphens, and must not begin with a number.
```

## 원인

- `CentralAgentView`가 `QuestionSnapshot.id`를 그대로 Textual `Button.id`에 포함했다.
- 모델 기반 synthesis가 만든 질문 id는 한글, 공백, 깨진 인코딩 문자열을 포함할 수 있다.
- Textual widget id는 ASCII 영문자, 숫자, `_`, `-`만 허용하므로 질문 렌더링 중 `BadIdentifier`가 발생했다.

## 수정

- 버튼 id는 화면 순번 기반의 안전한 ASCII 값(`answer-q-1-1`)으로 고정했다.
- 실제 질문 id와 선택 답변은 `_button_answers` 매핑에만 보관한다.
- 버튼 클릭 시 화면 id가 아니라 매핑된 `QuestionAnswer(question_id, answer)`를 controller로 전달한다.
- 비ASCII 질문 id가 들어와도 렌더링과 답변 라우팅이 유지되는 회귀 테스트를 추가했다.

## 검증

```bash
/home/zaemi/.local/bin/uv run pytest tests/test_textual_app.py -q -k "central_agent or question_answer"
```

결과:

```text
3 passed, 38 deselected in 2.65s
```

```bash
/home/zaemi/.local/bin/uv run pytest tests/test_textual_app.py -q
```

결과:

```text
41 passed in 22.81s
```

```bash
/home/zaemi/.local/bin/uvx ruff check src/trinity/textual_app/widgets/central_agent.py tests/test_textual_app.py
```

결과:

```text
All checks passed!
```

```bash
/home/zaemi/.local/bin/uv run pytest -q
```

결과:

```text
1160 passed, 1 warning in 53.82s
```

남은 경고는 기존 `tests/test_error_handling.py::TestActiveAgents::test_returns_all_when_no_crashes`
AsyncMock runtime warning이다.
