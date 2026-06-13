# Workflow Event Cache

작성일: 2026-06-13

브랜치: `feature/current-workflow-operation-analysis`

## 변경 요약

- `WorkflowPersistence.load_events()`에 instance-local mtime/size cache를 추가했다.
- `events.jsonl`의 `st_mtime_ns`와 `st_size`가 변하지 않으면 JSONL 재파싱 없이 cached events를
  반환한다.
- 반환값은 얕은 copy로 제공해 호출자가 event dict를 수정해도 내부 cache가 오염되지 않게 했다.
- `append_event()`, `clear()`, `restore_archive()`는 events 파일을 바꾸므로 cache를 무효화한다.

## 검증

```text
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_workflow_persistence.py \
  tests/test_textual_snapshot.py::test_snapshot_loads_workflow_events_once_per_projection \
  tests/test_textual_snapshot.py::test_snapshot_large_event_log_uses_single_read_and_tail_limit \
  tests/test_performance_harness.py \
  -q
```

결과:

```text
13 passed in 0.45s
```

추가 확인:

```text
PYTHONPATH=src .venv/bin/python -m py_compile \
  src/trinity/workflow/persistence.py \
  tests/test_workflow_persistence.py \
  tests/harness/perf.py \
  tests/test_performance_harness.py

git diff --check
```

결과: 통과.

