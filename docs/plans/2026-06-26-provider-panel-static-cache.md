# Provider Panel Static Cache

## Context

`ProviderPanel` renders a fixed set of `Static` widgets for provider name,
status, metadata, and summary. The panel updates these fields frequently while
Nexus is collecting provider responses. Running providers also update the
status label on every activity frame.

Each update currently performs selector lookups such as
`query_one(".provider-status", Static)`, even though the widgets are stable for
the panel lifetime.

## Goal

Avoid repeated `query_one()` calls for fixed provider panel text widgets.

## Design

- Cache the fixed `Static` widgets when composing the panel.
- Add a small fallback helper for unusual paths where the cache is not already
  populated.
- Route `update_state()` and `set_activity_frame()` through the cached widgets.
- Keep existing text comparison and class-update behavior unchanged.

## Tests

- Add a focused provider panel cache test for running activity frames.
- Verify status frame updates use the cached status widget without querying.
- Keep existing provider panel update tests intact.

## Versioning

Patch release: `1.0.267` -> `1.0.268`.
