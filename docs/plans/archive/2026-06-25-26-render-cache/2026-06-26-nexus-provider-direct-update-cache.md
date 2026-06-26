# Nexus Provider Direct Update Cache

## Context

`NexusScreen.apply_snapshot()` already skips provider panel updates when the
projected `ProviderPanelState` has not changed. The direct `update_provider()`
path still queries the provider panel, calls `update_state()`, and clears the
snapshot identity cache even when the incoming status and summary are identical
to the last applied state.

This path is narrow, but it is still part of the live Nexus status surface. When
workflow events repeat the same provider status, the screen should keep the UI
quiet and avoid invalidating caches that protect later snapshot application.

## Goal

Skip unchanged direct provider updates before querying the widget tree.

## Design

- Build the next `ProviderPanelState` from the configured agent spec first.
- Compare it with `_provider_state_cache[name]`.
- If unchanged, return without querying the panel, updating the widget, or
  resetting `_applied_snapshot_identity`.
- If changed, keep the existing behavior:
  - update the provider panel
  - store the new provider state cache entry
  - invalidate the snapshot identity cache
  - apply the current activity frame

Activity animation remains driven by `advance_activity_frame()` and
`_apply_activity_frame()`, so skipping identical direct state updates does not
stop running indicator refreshes.

## Tests

- Extend the Nexus provider cache tests with a direct `update_provider()` case.
- Verify repeated identical direct updates skip panel lookup/update.
- Verify changed direct updates still reach the panel and invalidate the snapshot
  identity behavior covered by the existing test.

## Versioning

Patch release: `1.0.253` -> `1.0.254`.
