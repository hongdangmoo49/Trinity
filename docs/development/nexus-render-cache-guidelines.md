# Nexus Render Cache Guidelines

This document records the render/cache rules established after the Nexus
performance pass.

## Why This Exists

The Nexus UI now uses many small caches:

- snapshot projection cache
- widget lookup caches
- render-key caches
- identity guards
- field-level update guards
- query/filter normalization caches

These caches were added locally to remove repeated Textual work during frequent
workflow snapshot and log updates. Do not consolidate them into a generic cache
manager unless two widgets share the same invalidation contract.

## Cache Families

### Snapshot Projection Cache

Primary owner:

- `src/trinity/textual_app/snapshot.py`

Invalidation inputs:

- workflow session file metadata
- workflow event file metadata
- shared context file metadata
- config state
- recent event identity

Focused tests:

- `tests/test_textual_snapshot.py`
- `tests/test_workflow_persistence.py`

### Screen/Widget Identity Guards

Primary owners:

- `src/trinity/textual_app/screens/nexus.py`
- `src/trinity/textual_app/screens/execution_matrix.py`
- `src/trinity/textual_app/screens/report.py`
- `src/trinity/textual_app/widgets/central_agent.py`
- `src/trinity/textual_app/widgets/inspector.py`

Use identity guards when applying the exact same snapshot or report object again
would only repeat field updates.

Focused tests:

- `tests/test_nexus_snapshot_identity_cache.py`
- `tests/test_execution_matrix_state_cache.py`
- `tests/test_report_screen_identity_cache.py`
- `tests/test_workflow_inspector_cache.py`
- `tests/test_central_agent_view.py`

### Widget Lookup Caches

Primary owners:

- Provider panels
- Execution rows
- Workspace picker
- Settings screen
- Prompt composer
- Execution retry modal

Use widget lookup caches only for stable child widgets that are rebound after
`compose()` or recompose.

Focused tests:

- `tests/test_nexus_screen_widget_cache.py`
- `tests/test_execution_log_modal_cache.py`
- `tests/test_resume_picker_cache.py`
- `tests/test_textual_workspace_picker.py`
- `tests/test_textual_settings.py`
- `tests/test_prompt_composer_palette_cache.py`

### Render-Key Caches

Render keys should be tuples of values that directly affect visible output.
Avoid storing full mutable snapshot objects in a render key unless identity is
the intended contract.

Good render-key values:

- ids
- status strings
- selected option names
- normalized search text
- counts
- stable labels

Risky render-key values:

- large raw logs
- full provider output blobs
- mutable lists
- timestamps that do not affect display

## Recompose Rule

Every cache that stores widget references must be reset after recompose or after
the owning screen/widget rebuilds its children.

Use local reset methods such as:

- `_reset_widget_cache`
- `_reset_render_cache`

Do not share a reset method across widgets unless they share the same lifecycle.

## Log Area Rule

Execution logs should keep bounded visible windows and append-only fast paths
where possible. Full historical logs belong in modal/search surfaces, not in
the always-visible Nexus area.

Focused tests:

- `tests/test_execution_log_modal_cache.py`
- `tests/test_execution_matrix_state_cache.py`

## Performance Tests

Run focused cache tests for touched widgets. For broad cache changes, run:

```bash
uv run pytest -q \
  tests/test_performance_harness.py \
  tests/test_textual_snapshot.py \
  tests/test_execution_matrix_state_cache.py \
  tests/test_nexus_snapshot_identity_cache.py \
  tests/test_report_screen_identity_cache.py
```

Run required smoke before merging shared Textual cache changes:

```bash
uv run python scripts/run_required_smoke_tests.py -q
```

## Consolidation Rule

Consolidate only after all of these are true:

1. Two caches share the same invalidation inputs.
2. Tests prove recompose rebinding for both owners.
3. The shared helper reduces code without hiding widget-specific lifecycle
   behavior.
4. The helper does not force unrelated widgets to import each other.

Until then, prefer small local caches with focused tests.
