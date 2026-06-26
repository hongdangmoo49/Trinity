# Execution Log Modal Widget Cache

## Context

`ExecutionLogModal` shows the full execution activity log and supports local
search. It already normalizes search queries and caches the rendered status text
and rendered lines, so unchanged searches do not repaint. When the visible
status or rendered lines change, the modal still resolves the fixed status
`Static` and log `RichLog` with `query_one()`.

The modal has a stable layout after compose, so those fixed widgets can be
cached.

## Goal

Avoid repeated selector lookups during execution log modal search refreshes.

## Design

- Cache the search status `Static` and log body `RichLog` during compose.
- Route `_refresh_log()` through cache helpers with query fallbacks.
- Reset widget caches before compose so future recomposition cannot hold stale
  references.
- Preserve existing query normalization, status text, and rendered lines caches.

## Tests

- Add a focused test that verifies changed search results reuse composed fixed
  widgets without selector lookups.
- Keep existing unchanged render state and query normalization tests intact.

## Versioning

Patch release: `1.0.278` -> `1.0.279`.
