# Settings Screen Control Cache

## Context

`SettingsScreen` builds a fixed set of `Select` controls plus fixed preview and
status `Static` widgets. `action_apply()` reads every setting and model value
through `_value()`, which currently performs `query_one()` for each select.
Preview/status updates also resolve fixed widgets by selector.

The visible values are already cached to skip unchanged updates. This change
targets the remaining fixed-control lookup cost when settings are applied.

## Goal

Avoid repeated selector lookups for settings screen controls after compose.

## Design

- Cache `Select` controls by id when `_select()` constructs them.
- Cache preview and status `Static` widgets when composing them.
- Route `_value()`, `_set_preview_text()`, and `_set_status_text()` through
  cache helpers with query fallbacks.
- Preserve existing preview/status text equality checks.

## Tests

- Extend settings screen cache tests to verify apply reads cached controls.
- Verify preview/status updates use cached widgets.
- Keep existing settings persistence and preview tests intact.

## Versioning

Patch release: `1.0.270` -> `1.0.271`.
