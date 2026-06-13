# P2/P3 Remaining Hardening

Date: 2026-06-13

Branch: `codex/p2-p3-scalability-hardening`

## Scope

- Added a `SharedContextEngine.pack_context_for_prompt()` cache keyed by shared context stat,
  memory index aggregate stats, workflow id, prompt budget, and recent record limit.
- Added a report artifact manifest for execution result and fallback attempt raw response paths.
- Changed provider inspector truncation to tail-first rendering so the most recent error/result stays visible.
- Reused one review aggregation index during snapshot projection for work package reviews and final review.
- Limited workflow history projection in Textual snapshots to the latest 500 events plus an omitted-count marker.
- Added a replay/report harness for persisted workflow session, events, raw artifacts, snapshot, and report reconstruction.

## Behavior

- Repeated provider prompt context packing avoids reparsing unchanged `shared.md` and rereading recent
  memory records.
- Report views can show artifact path, existence, size, and modified time without reading raw artifact bodies.
- Large provider output previews preserve the tail and tell users how many characters were omitted.
- Snapshot review projection parses persisted review results once per snapshot.
- Nexus/context projections avoid formatting thousands of workflow events for every route update.
- Replay tests can catch missing fallback reasons, artifact manifests, and review aggregation regressions
  without invoking real provider CLIs.

## Validation

```bash
PYTHONPATH=src python3 -m py_compile \
  src/trinity/context/shared.py \
  src/trinity/textual_app/snapshot.py \
  src/trinity/tui/report.py \
  src/trinity/textual_app/screens/report.py \
  src/trinity/textual_app/widgets/provider_inspector.py \
  tests/test_context_memory.py \
  tests/test_report.py \
  tests/test_textual_snapshot.py \
  tests/test_textual_app.py
# passed

PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_context_memory.py \
  tests/test_report.py \
  tests/test_textual_snapshot.py \
  tests/test_textual_app.py::test_provider_inspector_truncates_large_raw_output -q
# 59 passed

PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_context_memory.py \
  tests/test_report.py \
  tests/test_textual_snapshot.py \
  tests/test_textual_app.py \
  tests/test_performance_harness.py \
  tests/test_workflow_persistence.py \
  tests/test_replay_harness.py -q
# 197 passed
```
