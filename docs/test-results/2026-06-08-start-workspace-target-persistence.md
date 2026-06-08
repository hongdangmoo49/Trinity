# Start workspace target persistence

날짜: 2026-06-08
브랜치: `codex/review-workflow-design`

## 문제

Textual Start 화면에서 `Choose now`로 target workspace를 선택해도 값이
`TrinityTextualApp.workspace_candidate`에만 남고, 새 workflow session의
`target_workspace`에는 저장되지 않았다.

그 결과 사용자가 첫 페이지에서 폴더를 선택한 뒤 Nexus에서 `/execute`를 실행하면
workflow 기준 target workspace가 없다고 판단되어 workspace picker가 다시 열렸다.
세션을 resume한 경우에도 같은 문제가 발생할 수 있었다.

## 수정

- `TextualWorkflowController.start_prompt()`가 선택적 `target_workspace`를 받아,
  `WorkflowEngine.start()`로 새 session을 만든 직후 provider thread 시작 전에
  `WorkflowEngine.set_target_workspace()`를 호출하도록 했다.
- `TrinityTextualApp.on_start_screen_submitted()`가 Start 화면의 workspace candidate를
  안전한 target workspace로 전달한다.
- Trinity control repo 내부 경로는 즉시 저장하지 않고 기존 실행 전 확인 흐름을 유지한다.

## 효과

- 첫 페이지에서 선택한 안전한 target workspace가 `.trinity/workflow/session.json`에
  저장된다.
- 같은 session이나 resume 이후 Nexus에서 `/execute`를 눌러도 같은 target workspace를
  재사용한다.
- control repo 내부 실행은 여전히 명시적 확인 없이는 target으로 확정되지 않는다.

## 검증

```text
uv run pytest tests/test_textual_app.py::test_start_submission_persists_selected_workspace_target tests/test_textual_app.py::test_start_choose_now_updates_workspace_candidate tests/test_textual_app.py::test_start_screen_submission_moves_to_nexus -q
```

결과:

```text
3 passed in 2.88s
```

추가 전체 검증:

```text
uv run pytest -q
```

결과:

```text
1294 passed, 1 warning in 99.81s
```

경고:

- `tests/test_e2e.py::TestE2EContext::test_context_shows_shared`의 기존
  `AsyncMock` unawaited warning.
