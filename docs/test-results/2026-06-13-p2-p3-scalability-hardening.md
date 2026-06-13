# P2/P3 Scalability Hardening

Date: 2026-06-13

Branch: `codex/p2-p3-scalability-hardening`

## Scope

- Added an archive summary manifest at `.trinity/workflow/history/manifest.json`.
- Added a workflow event offset index at `.trinity/workflow/events.index.jsonl`.
- Changed Textual artifact preview reads to bounded byte reads so large raw artifacts are not fully loaded before truncation.

## Behavior

### Archive Manifest

- `WorkflowPersistence.archive_active_session()` refreshes a summary manifest after archiving.
- `WorkflowPersistence.list_archives()` uses the manifest when it matches the archive files.
- If the manifest is missing, stale, corrupted, or does not match the history directory, Trinity falls back to scanning archive JSON files and rewrites the manifest.
- `restore_archive()` still restores from the full archive JSON file and returns the full restored session.

### Event Index

- `append_event()` writes JSONL as bytes and appends offset metadata to
  `.trinity/workflow/events.index.jsonl`.
- `load_events_for_workflow()` uses workflow-specific offsets when the index is valid.
- If the index is missing or stale, it is rebuilt from `events.jsonl`.
- `clear()` and `restore_archive()` invalidate the active event index.

### Artifact Preview

- Snapshot artifact reads now read at most `limit + 1` bytes.
- Large raw provider artifacts are represented by bounded previews instead of full in-memory reads.

## Validation

```bash
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_workflow_persistence.py \
  tests/test_textual_snapshot.py \
  tests/test_performance_harness.py -q
# 47 passed

PYTHONPATH=src .venv/bin/python -m pytest tests/test_textual_app.py -q
# 123 passed

PYTHONPATH=src .venv/bin/python -m py_compile \
  src/trinity/workflow/persistence.py \
  src/trinity/textual_app/snapshot.py
# passed
```
