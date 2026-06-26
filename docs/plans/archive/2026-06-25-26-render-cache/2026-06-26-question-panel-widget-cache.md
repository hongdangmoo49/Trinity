# Question Panel Widget Cache

## Context

`QuestionPanel` renders central-agent questions in the Nexus page. It already
keeps a normalized question key, empty-state key, and title key to skip
unchanged renders, but the render path still resolves the fixed title and body
widgets with `query_one()`.

The panel receives snapshot updates from the Nexus screen, so avoiding repeated
fixed-widget lookups keeps frequent refreshes cheaper.

## Goal

Reuse the composed title and body widgets for question updates.

## Design

- Cache the title `Static` and body `Vertical` when composing the panel.
- Route title updates and body rerenders through cache helpers with query
  fallbacks.
- Reset the cached references before compose so a future recompose cannot keep
  stale widget instances.
- Preserve the existing question key, title key, and empty-state checks.

## Tests

- Add a focused test that verifies question updates reuse composed fixed
  widgets instead of querying by selector.
- Keep existing title, render skip, empty-state, and question display tests
  intact.

## Versioning

Patch release: `1.0.272` -> `1.0.273`.
