# Execution Timeline Logging

작성일: 2026-06-06

브랜치: `codex/execution-matrix-hardening`

## 문제

Execution Matrix에서 work package의 시작과 완료는 보였지만, 각 WP가 실제로 언제
시작했고 언제 끝났는지 화면 로그만으로는 확인할 수 없었다.

## 수정

- `ExecutionProtocol`이 `WORK_PACKAGE_STARTED`와 `WORK_PACKAGE_COMPLETED` 이벤트에
  provider 실행 프로토콜 기준 발생 시각(`occurred_at`)을 포함한다.
- `WorkflowEngine`은 runtime event를 JSONL에 저장할 때 polling 시각이 아니라
  `occurred_at`을 event `timestamp`로 보존한다.
- Textual Workbench와 Rich TUI execution loop가 완료 이벤트도 persistence에 기록한다.
- Execution Matrix snapshot은 최근 workflow event를 20개에서 80개까지 표시하고,
  `work_package_started`/`work_package_completed` 로그 앞에 `[HH:MM:SS]`를 붙인다.
- 완료 이벤트가 있는 패키지는 별도 execution result summary를 중복 표시하지 않는다.

예시:

```text
[14:01:03] work_package_started: WP-001 claude running
[14:05:42] work_package_completed: WP-001 claude done - Implemented input handling.
```

## 검증

```bash
/home/zaemi/.local/bin/uv run pytest tests/test_textual_snapshot.py tests/test_workflow_engine.py::test_record_work_package_started_persists_running_status tests/test_workflow_engine.py::test_record_work_package_completed_persists_finished_event tests/test_execution_protocol.py::test_execution_protocol_dispatches_package_and_records_result -q
```

결과:

```text
13 passed in 0.10s
```

```bash
/home/zaemi/.local/bin/uv run pytest tests/test_tui_session.py -k execution_live_loop_persists_incremental_package_progress -q
```

결과:

```text
1 passed, 77 deselected in 0.19s
```

```bash
/home/zaemi/.local/bin/uv run pytest tests/test_textual_app.py tests/test_tui_session.py tests/test_workflow_engine.py tests/test_execution_protocol.py -q
```

결과:

```text
160 passed in 17.54s
```

```bash
/home/zaemi/.local/bin/uvx ruff check src/trinity/workflow/execution.py src/trinity/workflow/engine.py src/trinity/textual_app/workflow_controller.py src/trinity/tui/session.py src/trinity/textual_app/snapshot.py tests/test_textual_snapshot.py tests/test_workflow_engine.py
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
1164 passed, 1 warning in 44.79s
```

남은 경고는 기존 AsyncMock runtime warning 계열이다.
