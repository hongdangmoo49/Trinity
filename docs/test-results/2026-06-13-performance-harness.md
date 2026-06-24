# Performance Harness Skeleton

작성일: 2026-06-13

브랜치: `feature/current-workflow-operation-analysis`

## 변경 요약

- `tests/harness/perf.py`에 deterministic workflow 성능 fixture를 추가했다.
- fixture는 work package, execution result, review result, event log, shared context 크기를
  파라미터로 조정할 수 있다.
- `measure_ms()`와 `snapshot_probe()`로 snapshot/event load의 기준 시간을 테스트에서
  반복 측정할 수 있게 했다.
- `tests/test_performance_harness.py`에 smoke 테스트를 추가해 fixture가 session, events,
  shared context, Nexus snapshot 경로를 실제로 자극하는지 검증했다.

## 2026-06-24 업데이트

- large workflow snapshot projection budget test를 추가했다.
- 해당 테스트는 wall-clock threshold 대신 full event scan 금지, execution log cap,
  workflow event display cap을 검증한다.
- 이 테스트는 Report 화면 event tail, Workflow event index cache, snapshot fallback tail
  보강 이후의 회귀 방지 기준으로 사용한다.

## 검증

```text
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_performance_harness.py \
  tests/test_provider_model_discovery.py \
  tests/test_workflow_engine.py::test_record_execution_results_can_persist_progress_without_finalizing \
  -q
```

결과:

```text
12 passed in 0.17s
```

추가 확인:

```text
PYTHONPATH=src .venv/bin/python -m py_compile \
  tests/harness/__init__.py \
  tests/harness/perf.py \
  tests/test_performance_harness.py

git diff --check
```

결과: 통과.

## 남은 작업

- events cache, snapshot memoization, event index cache의 before/after 수치는 필요 시
  로컬 benchmark로 수집한다. CI gate는 안정성을 위해 구조적 budget test를 사용한다.
- provider model discovery cache-first/parallel refresh 작업에 별도 delay fixture를 추가한다.
- execution partial result의 UI/report 통합 계약을 하네스 scenario로 고정한다.
