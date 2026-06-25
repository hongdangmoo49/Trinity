# Execution Log Search Query Normalization

## Context

`ExecutionLogModal` filters log lines case-insensitively. However, the input
change handler compares raw stripped query text before refreshing the log. A
case-only change such as `fail` -> `FAIL` therefore triggers `_refresh_log()`
even though the visible result set and status text cannot change.

## Goal

Skip execution log refreshes when a search input change is semantically
unchanged for the current case-insensitive filter.

## Design

- Add a small query normalization helper for execution log searches.
- Compare input changes using the normalized key.
- Keep the existing `filter_query` value as the applied query text.
- Leave `_refresh_log()` result caching intact so this optimization only avoids
  needless refresh entry calls.

## Tests

- Extend execution log modal cache tests to cover case-only search changes.
- Verify unchanged normalized queries do not call `_refresh_log()`.
- Verify a genuinely different query still refreshes and updates
  `filter_query`.

## Versioning

Patch release: `1.0.263` -> `1.0.264`.
