# Execution Timeline Logging

작성일: 2026-06-06

브랜치: `codex/project-improvement-hardening`

## 문제

Execution Matrix에서 work package 실행이 병렬로 시작되는지는 로그의
`work_package_started` 행으로 추정할 수 있었지만, 각 WP가 언제 끝났는지와
시작/종료 시각을 같은 로그에서 확인하기 어려웠다.

기존 구조의 한계:

- `WORK_PACKAGE_STARTED` runtime event만 workflow event로 영속화했다.
- 완료는 `execution_result_recorded` 또는 session result fallback으로만 표시되어
  start/end timeline으로 읽기 어려웠다.
- workflow event의 `timestamp`는 event 소비 시각에 가까웠고, provider dispatch
  시각을 직접 전달하지 않았다.
- Execution Matrix snapshot은 최근 20개 event만 표시해 WP가 많으면 시작 이벤트가
  밀려날 수 있었다.

## 수정

- `ExecutionProtocol`이 runtime event payload에 `occurred_at`을 포함한다.
- `WorkflowEngine.record_work_package_started()`가 runtime timestamp를 event root
  `timestamp`로 보존한다.
- `WorkflowEngine.record_work_package_completed()`를 추가해 package id, agent,
  status, summary, timestamp를 `work_package_completed` event로 저장한다.
- Textual Workbench controller와 plain TUI live loop가 `WORK_PACKAGE_COMPLETED`
  event도 소비한다.
- Execution Matrix snapshot log가 event timestamp를 `[HH:MM:SS]`로 표시한다.
- 새 `work_package_completed` event가 있으면 같은 package의 legacy
  `execution_result_recorded`와 session result fallback 중복 표시를 숨긴다.
- 오래된 session 호환을 위해 `execution_result_recorded`는
  `work_package_completed` 형식으로 표시한다.

예상 표시:

```text
[14:01:03] work_package_started: WP-001 claude running
[14:05:42] work_package_completed: WP-001 claude done - Implemented input handling.
```

`events.jsonl`에는 같은 정보가 다음처럼 남는다.

```json
{"timestamp":1710000000.0,"event":"work_package_started","data":{"package_id":"WP-001","agent":"claude","status":"running"}}
{"timestamp":1710000060.0,"event":"work_package_completed","data":{"package_id":"WP-001","agent":"claude","status":"done","summary":"Implemented input handling."}}
```

## 검증

```bash
/home/zaemi/.local/bin/uv run pytest tests/test_execution_protocol.py::test_execution_protocol_dispatches_package_and_records_result tests/test_workflow_engine.py::test_record_work_package_started_persists_running_status tests/test_workflow_engine.py::test_record_work_package_completed_persists_finished_event tests/test_textual_snapshot.py::test_snapshot_formats_execution_events_with_runtime_details tests/test_textual_snapshot.py::test_snapshot_formats_legacy_execution_result_event tests/test_textual_snapshot.py::test_snapshot_hides_session_result_when_finished_event_is_visible tests/test_textual_workflow_controller.py::test_textual_workflow_controller_persists_work_package_runtime_events -q
```

결과:

```text
7 passed in 0.10s
```

```bash
/home/zaemi/.local/bin/uv run pytest tests/test_execution_protocol.py tests/test_workflow_engine.py tests/test_textual_snapshot.py tests/test_textual_workflow_controller.py tests/test_tui_session.py -q
```

결과:

```text
136 passed in 1.48s
```

```bash
/home/zaemi/.local/bin/uv run pytest tests/test_textual_app.py tests/test_textual_runtime.py tests/test_textual_smoke.py -q
```

결과:

```text
56 passed in 16.72s
```

```bash
/home/zaemi/.local/bin/uv run pytest tests/test_orchestrator.py tests/test_parallel_execution_policy.py -q
```

결과:

```text
35 passed in 0.24s
```

```bash
/home/zaemi/.local/bin/uvx ruff check src/trinity/workflow/execution.py src/trinity/workflow/engine.py src/trinity/textual_app/workflow_controller.py src/trinity/textual_app/snapshot.py src/trinity/tui/session.py tests/test_execution_protocol.py tests/test_workflow_engine.py tests/test_textual_snapshot.py tests/test_textual_workflow_controller.py tests/test_tui_session.py
```

결과:

```text
All checks passed!
```

```bash
python3 -m py_compile src/trinity/workflow/execution.py src/trinity/workflow/engine.py src/trinity/textual_app/workflow_controller.py src/trinity/textual_app/snapshot.py src/trinity/tui/session.py
```

결과: 통과.

```bash
/home/zaemi/.local/bin/uv run pytest -q
```

결과:

```text
1167 passed, 1 warning in 45.87s
```

남은 경고는 기존 `AsyncMock` runtime warning 계열이다.

추가로 전체 lint 범위를 확인했다.

```bash
/home/zaemi/.local/bin/uvx ruff check src tests
```

결과: 실패. 이번 변경 파일이 아니라 기존 전역 lint debt에서 다수의 unused import,
import order, unused variable 오류가 발견됐다. 이번 브랜치의 변경 파일 대상 ruff는
통과했다.
