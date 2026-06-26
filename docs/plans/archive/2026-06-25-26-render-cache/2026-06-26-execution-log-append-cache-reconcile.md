# Execution Log Append Cache Reconcile

## Context

`ExecutionMatrixScreen._render_log()` keeps a compact cache of the currently
rendered activity lines. When snapshot activity lines grow by prefix append, the
screen writes only the new tail. This avoids clearing and rewriting the whole
`RichLog` on every workflow update.

`append_log()` writes a runtime-only line directly to the `RichLog`, but it does
not change `_activity_lines_key`. If the next `apply_execution_state()` receives
a snapshot whose `execution_log` content is unchanged, `_render_log()` can treat
the log as already current and leave the runtime-only line on screen.

## Goal

Keep the append fast path while ensuring direct appended lines do not make the
snapshot-backed log cache stale.

## Design

- When `append_log()` writes a direct runtime line, clear `_activity_lines_key`.
- Keep invalidating `_applied_state_identity` so the next snapshot application
  still reaches `_render_log()`.
- Let `_render_log()` reconcile the visible log from snapshot activity lines:
  - unchanged snapshot lines after a direct append should clear/rewrite the
    compact snapshot view
  - true prefix growth should still append only the new tail

## Tests

- Extend execution activity log tests with a direct append followed by the same
  snapshot log.
- Assert the next snapshot render clears the direct append and writes the
  snapshot-backed compact log.
- Keep existing prefix append and recent-window replacement tests intact.

## Versioning

Patch release: `1.0.254` -> `1.0.255`.
