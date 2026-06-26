# Execution Matrix Fixed Widget Cache

## Context

`ExecutionMatrixScreen` already caches row render keys, package row widgets,
activity-line keys, chrome projections, and state identity. The remaining screen
update paths still resolve fixed widgets such as the header, summary, toggle
buttons, retry button, package list, shell container, and log with `query_one()`.

The execution page is a high-frequency UI surface: snapshot updates, task view
toggles, retry availability, and activity log updates can all happen while work
packages are running. Fixed-widget selector lookups should stay out of those
hot paths.

## Goal

Cache the fixed execution screen widgets composed once and reuse them during
chrome, package list, shell class, and log updates.

## Design

- Cache the execution shell, header, summary, task/activity toggle buttons,
  retry button, package list, and activity log when composing the screen.
- Route screen chrome updates, task-expanded class sync, package list rerenders,
  append-only log writes, and full log renders through cache helpers with query
  fallbacks.
- Reset fixed-widget caches before compose so a future recompose cannot keep
  stale widget instances.
- Preserve existing projection, row, activity line, and state identity caches.

## Tests

- Add a focused test that verifies execution screen updates reuse composed fixed
  widgets without selector lookups.
- Keep existing execution matrix state, append log, and task-expanded cache
  tests intact.

## Versioning

Patch release: `1.0.274` -> `1.0.275`.
