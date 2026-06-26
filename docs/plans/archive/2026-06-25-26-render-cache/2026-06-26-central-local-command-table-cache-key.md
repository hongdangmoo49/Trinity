# Central Local Command Table Cache Key

## Context

`CentralAgentView` renders the latest local command in two places:

- markdown summary, which includes command body and action hint
- optional `DataTable`, which uses only command, title, table columns, and rows

The local command table cache key currently includes body, action hint, and
empty-state fields that are not rendered by `_render_local_command_tables()`.
When only the command body changes, the markdown should update, but the table
can be kept as-is.

## Goal

Avoid rebuilding the central local command table when fields unrelated to the
table projection change.

## Design

- Narrow `_local_command_key()` to the fields consumed by the table renderer:
  command, title, table columns, and table rows.
- Keep markdown rendering keyed by the generated markdown text.
- Preserve table rebuilds when the visible table title, columns, or rows change.

## Tests

- Add a central agent view cache test for a body-only local command update.
- Verify the table renderer is skipped for body-only changes.
- Verify the table renderer still runs when table rows change.

## Versioning

Patch release: `1.0.264` -> `1.0.265`.
