# Execution Retry Modal Widget Cache

## Context

`ExecutionRetryModal` updates the selected package summary and retry confirm
button when custom retry selections change. The summary text and disabled state
already have value caches, but `_refresh_selection_state()` still resolves the
fixed widgets with `query_one()` during refreshes.

This modal can be revisited while execution recovery is active, so keeping the
selection refresh path small helps avoid avoidable selector work on repeated
checkbox changes.

## Goal

Avoid repeated fixed-widget selector lookups while preserving retry selection
behavior.

## Design

- Add lazy caches for the selected summary `Static` and confirm `Button`.
- Reset those widget caches before each compose so recomposed modal content is
  not tied to stale widget instances.
- Only touch the confirm button when the disabled value actually changes.
- Keep existing selected text and disabled-state equality checks.

## Tests

- Extend execution retry modal tests to verify repeated state refreshes reuse
  cached fixed widgets.
- Keep existing selection update, disabled button, and filter recompose tests
  intact.

## Versioning

Patch release: `1.0.271` -> `1.0.272`.
