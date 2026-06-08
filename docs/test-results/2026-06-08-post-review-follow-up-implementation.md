# Post-review Follow-up Implementation Test Results

작성일: 2026-06-08

브랜치: `codex/review-workflow-design`

## 구현 요약

- Final review 완료 후 workflow를 즉시 `done`으로 닫지 않고 `post_review_ready`로 전환한다.
- Review 결과에서 `PostReviewActionItem`을 추출하고 session에 저장한다.
- `/improve` 명령으로 action item 선택, 자유 보강 요청, `/improve done` 종료를 처리한다.
- 선택된 action item은 기존 workflow에 `WP-S001` 형식의 supplemental WP로 append된다.
- 기존 `execution_results`, `review_results`, decision log는 보강 작업 시작 시 삭제하지 않는다.
- Textual central panel, inspector, local command result와 plain TUI에 post-review 상태를 표시한다.

## 검증

```bash
uv run pytest tests/test_peer_review.py tests/test_workflow_engine.py tests/test_textual_snapshot.py tests/test_textual_workflow_controller.py tests/test_tui_session.py tests/test_slash_command_docs.py -q
```

결과:

```text
172 passed in 2.03s
```

```bash
uv run pytest -q
```

결과:

```text
1293 passed, 1 warning in 80.06s
```

남은 warning은 기존 `tests/test_e2e.py::TestE2EContext::test_context_shows_shared`
계열의 `AsyncMock` unawaited warning이다. 이번 post-review 구현에서 새로 도입된 실패는 아니다.

## 정적 검사

`pyproject.toml`에는 `[tool.ruff]` 설정이 있으나 현재 WSL 환경의 `uv run ruff check .`는
`ruff` 실행 파일을 찾지 못해 수행하지 못했다.
