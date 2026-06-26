# Execution Package Row Widget Cache

## Context

`ExecutionMatrixScreen` already keeps `ExecutionPackageRow` instances stable
when the package order and action structure are unchanged. The row then updates
only changed text fields through `ExecutionPackageRow.update_projection()`.

Inside each row update, fixed child widgets are still resolved with selectors
such as `.execution-package-status` and `.execution-package-spec`. Large
workflows can update a small subset of rows repeatedly, so these per-row lookup
costs are still avoidable.

## Goal

Avoid repeated selector lookups for fixed widgets inside a reused execution
package row.

## Design

- Cache row `Static` widgets while composing the row.
- Cache stable action `Button` widgets while composing the row.
- Route field and button updates through cache helpers with query fallbacks.
- Keep existing list-level behavior unchanged: action structure changes still
  remount rows through `ExecutionMatrixScreen`.

## Tests

- Extend execution package row tests to verify status-only updates do not query
  row children after mount.
- Verify detail button label/disabled updates also use the cached button.
- Keep large execution matrix row-reuse tests intact.

## Versioning

Patch release: `1.0.268` -> `1.0.269`.
