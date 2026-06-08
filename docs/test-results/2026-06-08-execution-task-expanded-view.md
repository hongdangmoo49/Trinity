# Execution Task Expanded View

날짜: 2026-06-08
브랜치: `codex/execution-task-expanded-view`

## 변경 요약

Execution Matrix의 task 목록 영역을 확장/축소할 수 있게 했다.

- `f` 키로 task 영역 확대/축소
- `Expand Tasks` / `Compact Tasks` 버튼 제공
- 확장 상태에서 package list를 화면 대부분으로 확대
- 확장 상태에서 task title clip width를 `28`에서 `72`로 확대
- execution log는 하단 작은 영역으로 유지
- 기존 `Spec` 버튼과 WP detail modal 동작 유지
- `Spec` 버튼 클릭 시 WP detail modal이 열리는지 검증

## 검증

```text
uv run pytest tests/test_textual_app.py::test_execution_matrix_expands_task_area tests/test_textual_app.py::test_execution_matrix_separates_owner_and_executor tests/test_textual_app.py::test_execution_matrix_renders_preflight_and_packages -q
```

결과:

```text
3 passed in 2.54s
```

```text
uv run python -m py_compile src/trinity/textual_app/screens/execution_matrix.py
```

결과: 통과.

전체 회귀:

```text
uv run pytest -q
```

결과:

```text
1297 passed, 1 warning in 90.36s
```

경고:

- `tests/test_e2e.py::TestE2EContext::test_context_shows_shared`의 기존
  `AsyncMock` unawaited warning.
