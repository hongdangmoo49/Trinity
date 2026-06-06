# Follow-up Target Workspace Reuse

작성일: 2026-06-06

브랜치: `codex/project-improvement-hardening`

## 문제

사용자가 Execution 화면에서 `testfolder` 같은 target workspace를 선택해 프로젝트를
생성한 뒤 Nexus로 돌아와 `테스트를 해라` 같은 후속 명령을 입력하면, 다음 Execute에서
다시 workspace picker가 열렸다.

사용자 경험상 같은 Nexus session에서 입력한 후속 명령은 직전에 만든 target workspace를
대상으로 한다. 하지만 기존 routing은 `BLUEPRINT_READY` 상태에서만 기존 blueprint
workflow로 이어지고, 실행 후 `REVIEWING`/`DONE` 상태에서는 새 workflow를 시작했다.
새 workflow에는 `target_workspace`가 없으므로 Execute preflight가 다시 폴더를 요구했다.

## 수정

- 기존 blueprint가 있는 workflow는 `BLUEPRINT_READY`, `REVIEWING`, `DONE`,
  `FAILED` 상태에서 follow-up text를 기존 workflow continuation으로 처리한다.
- `continue_from_blueprint()`는 이전 상태를 `workflow_continued.data.source_state`에
  기록한다.
- follow-up deliberation 이후 새 blueprint가 준비되어도 기존 `target_workspace`를
  유지한다.

## 효과

같은 Nexus session에서 다음 흐름이 자연스럽게 이어진다.

```text
testfolder 선택
-> 프로젝트 생성 실행
-> Nexus에서 "테스트를 해라"
-> agents가 테스트 계획/blueprint 생성
-> Execute
-> workspace picker 없이 기존 testfolder에서 실행
```

새 workspace가 필요하면 사용자가 명시적으로 새 workflow를 시작하거나 target을
변경해야 한다.

## 검증

```bash
/home/zaemi/.local/bin/uv run pytest tests/test_workflow_engine.py::test_reviewing_followup_keeps_existing_workflow_and_target_workspace tests/test_workflow_engine.py::test_followup_result_can_execute_without_reselecting_target_workspace tests/test_textual_workflow_controller.py::test_textual_workflow_controller_reuses_target_for_review_followup -q
```

결과:

```text
3 passed in 0.40s
```

```bash
/home/zaemi/.local/bin/uv run pytest tests/test_workflow_engine.py tests/test_textual_workflow_controller.py tests/test_textual_app.py -q
```

결과:

```text
74 passed in 25.88s
```

```bash
/home/zaemi/.local/bin/uvx ruff check src/trinity/workflow/engine.py tests/test_workflow_engine.py tests/test_textual_workflow_controller.py
```

결과:

```text
All checks passed!
```

```bash
python3 -m py_compile src/trinity/workflow/engine.py
```

결과: 통과.

```bash
/home/zaemi/.local/bin/uv run pytest -q
```

결과:

```text
1170 passed, 1 warning in 57.65s
```

남은 경고는 기존 `AsyncMock` runtime warning 계열이다.
