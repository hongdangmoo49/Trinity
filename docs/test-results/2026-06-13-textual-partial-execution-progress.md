# Textual Partial Execution Progress

작성일: 2026-06-13

브랜치: `feature/current-workflow-operation-analysis`

## 변경 요약

- Textual workflow controller가 execution `result_callback`을 orchestrator에 전달하도록 했다.
- callback은 background execution thread에서 결과를 직접 기록하지 않고, controller 내부 progress
  queue에 추가한다.
- `drain_updates()`가 progress queue를 비우며
  `workflow.record_execution_results(..., finalize=False, emit_events=False)`로 session에 upsert한다.
- 전체 execution worker가 끝나기 전에도 완료된 WP 결과가 snapshot/report projection의 source가 되는
  `session.execution_results`에 반영된다.
- 최종 completion 처리에서는 기존처럼 `emit_events=False`로 전체 결과를 다시 upsert하므로 중복 event를
  만들지 않는다.

## 검증

```text
PYTHONPATH=src .venv/bin/python -m pytest tests/test_textual_workflow_controller.py -q
```

결과:

```text
31 passed in 1.34s
```

관련 projection 회귀:

```text
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_textual_workflow_controller.py \
  tests/test_textual_snapshot.py \
  tests/test_performance_harness.py \
  -q
```

결과:

```text
65 passed in 2.07s
```

추가 확인:

```text
PYTHONPATH=src .venv/bin/python -m py_compile \
  src/trinity/textual_app/workflow_controller.py \
  tests/test_textual_workflow_controller.py

git diff --check
```

결과: 통과.

