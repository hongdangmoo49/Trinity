# Project Improvement Hardening Plan

작성일: 2026-06-06

브랜치: `codex/project-improvement-hardening`

기준:

- control repo: `/home/zaemi/workspace/Trinity`
- base branch: `main`
- package/CLI version: `0.10.2`
- latest observed baseline: `main` includes Execution Matrix hardening, workspace picker latency,
  question ID hardening, and execution failure hardening.

## 목표

최근 `0.10.2` 실행 흐름에서 사용자가 실제로 확인해야 하는 정보는
work package가 병렬로 언제 시작됐고 언제 끝났는지, 실패했다면 왜 실패했는지다.
현재 main은 실패/blocked 사유와 timeout 분리는 개선했지만, 각 WP의 start/end
타임라인은 아직 충분히 영속화하지 않는다.

이번 브랜치는 다음 순서로 개선한다.

1. Execution Matrix와 `.trinity/workflow/events.jsonl`에서 WP 시작/종료 시각을
   직접 확인할 수 있게 한다.
2. 오래된 `execution_result_recorded` 이벤트와 새 완료 이벤트가 동시에 보일 때
   중복 로그가 생기지 않게 한다.
3. 운영 문서와 테스트 결과 문서를 갱신해 사용자가 검증 경로를 바로 찾을 수 있게 한다.

## 확인한 현재 상태

### 1. 시작 이벤트만 영속화됨

`WorkflowEngine.record_work_package_started()`는 `work_package_started` 이벤트를
남기지만, 완료 시점에 대응되는 `work_package_completed` 영속 이벤트가 없다.
현재 완료 결과는 `record_execution_results()`가 `execution_result_recorded`로만
남긴다.

영향:

- Execution Matrix는 `work_package_started`와 결과 요약을 따로 조합해야 한다.
- 이벤트 로그만 보면 각 WP의 종료 시각과 duration을 직접 계산하기 어렵다.
- 긴 실행에서 `session.execution_results` fallback과 이벤트 로그가 중복 표시될 수 있다.

### 2. TUI runtime event 시간과 persisted event 시간이 분리되지 않음

`ExecutionProtocol`은 TUI event를 발생시키지만 event payload에는 발생 시각이 없다.
Textual controller/plain TUI가 나중에 poll하면서 workflow event를 기록하면,
실제 provider 작업 시작/종료 시간이 아니라 소비 시각이 저장될 수 있다.

영향:

- 병렬 실행 여부를 검증할 때 start timestamp가 실제 dispatch 순간을 충분히
  대표하지 못할 수 있다.
- 사용자가 “각 WP를 언제 시작해서 언제 끝냈는지” 확인하려면 raw runtime 시각이 필요하다.

### 3. Snapshot execution log의 관측 폭이 좁음

`NexusSnapshotAdapter._execution_log()`는 최근 20개 event와 최근 10개 result를
합쳐 보여준다. WP 10개만 실행해도 start/end 이벤트가 20개를 넘기 때문에,
긴 실행에서는 앞부분 start 이벤트가 사라질 수 있다.

영향:

- 사용자는 병렬 start batch가 실제로 같은 시각대에 시작됐는지 보기 어렵다.
- 완료 이벤트를 추가하면 중복/구형 이벤트 호환 처리 없이는 로그가 더 복잡해진다.

## 작업 단위

### Task A. WP timeline event hardening

소유 파일:

- `src/trinity/workflow/execution.py`
- `src/trinity/workflow/engine.py`
- `src/trinity/textual_app/workflow_controller.py`
- `src/trinity/tui/session.py`

작업:

- `ExecutionProtocol._emit()`가 `occurred_at`을 event payload에 포함한다.
- `WorkflowEngine.record_work_package_started()`가 runtime `occurred_at`을 받을 수 있게 한다.
- `WorkflowEngine.record_work_package_completed()`를 추가해 package id, agent, status,
  summary, occurred_at을 영속화한다.
- Textual controller와 plain TUI session이 `WORK_PACKAGE_COMPLETED`를 소비해
  완료 이벤트를 기록한다.

검증:

- `tests/test_workflow_engine.py`
- `tests/test_textual_workflow_controller.py` 또는 관련 runtime event 테스트
- `tests/test_tui_session.py`

### Task B. Execution Matrix log formatting

소유 파일:

- `src/trinity/textual_app/snapshot.py`
- `tests/test_textual_snapshot.py`

작업:

- execution log event window를 넓힌다.
- event timestamp를 `[HH:MM:SS]` 형식으로 표시한다.
- 새 `work_package_completed` 이벤트가 있으면 같은 package의
  `execution_result_recorded`/session result fallback 중복을 숨긴다.
- 오래된 로그 호환을 위해 `execution_result_recorded`는 완료 이벤트처럼 표시한다.

검증:

- timestamp가 있는 start/end 이벤트가 expected log에 포함된다.
- 완료 이벤트와 session result가 동시에 있을 때 중복이 사라진다.
- 오래된 `execution_result_recorded`만 있는 session도 계속 표시된다.

### Task C. Documentation and checkpoint sync

소유 파일:

- `docs/workflow-v0.10.2-guide.md`
- `docs/checkpoint.md`
- `docs/test-results/2026-06-06-execution-timeline-logging.md`

작업:

- 사용자가 Execution Matrix와 `events.jsonl`에서 확인할 수 있는 start/end
  로그 형식을 문서화한다.
- 검증 명령과 결과를 별도 test-results 문서로 남긴다.
- checkpoint 최신 운영 문서 목록에 이번 결과를 추가한다.

검증:

- `git diff --check`
- 변경 파일 대상 ruff/pytest
- 전체 `uv run pytest -q`

## 병렬화 판단

Task A와 Task B는 모두 workflow execution log를 다루지만 쓰기 영역이 다르다.
단, Task B는 Task A의 최종 event schema를 알아야 하므로 explorer로 선행 조사만
병렬화하고, 실제 통합 패치는 주 작업자가 순서대로 적용한다.

Task C는 코드 schema가 확정된 뒤 수행해야 하므로 코드 패치 이후 독립 문서 작업으로
분리해 커밋한다.
