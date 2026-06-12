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

- 성능 fixture를 사용해 events cache와 snapshot memoization 변경의 before/after를 비교한다.
- provider model discovery cache-first/parallel refresh 작업에 별도 delay fixture를 추가한다.
- execution partial result의 UI/report 통합 계약을 하네스 scenario로 고정한다.

