# 세션형 Workflow UI 테스트 결과

## 변경 요약

- `needs_user_decision` 상태에서 일반 텍스트 입력을 다음 질문 답변으로 처리하도록 변경했다.
- `blueprint_ready` 상태에서 일반 텍스트가 기존 workflow를 잃지 않도록 후속 행동 선택 UI를 추가했다.
- `/execute [text]` 명령을 추가해 현재 승인된 blueprint를 실행 가능한 work package로 재생성하고 즉시 실행할 수 있게 했다.
- 직접 execution-only 실행에서도 agent wrapper가 start되도록 orchestrator 실행 경로를 보정했다.
- planning-only work package는 TUI에서 `planning_only`로 표시하도록 변경했다.

## 검증

```text
uv run pytest tests/test_workflow_engine.py tests/test_tui_session.py tests/test_tui_prompt.py
99 passed in 0.74s
```

```text
uv run pytest
962 passed, 1 warning in 19.89s
```

## 남은 경고

- `tests/test_error_handling.py::TestActiveAgents::test_excludes_disabled`에서 기존 `AsyncMock` coroutine 미await 경고가 1건 발생했다.
- 테스트 실패는 아니며 이번 UI 변경과 직접 관련된 실패는 확인되지 않았다.
