# Nexus Activity Target State Cache

## Context

`NexusScreen.advance_activity_frame()` runs on the workflow polling tick. It
currently asks mounted widgets whether the central view or provider panels are
running before advancing the spinner frame.

The screen already has enough state to answer the same question without widget
tree lookups:

- the current workflow snapshot describes central activity
- `_provider_state_cache` stores the projected provider panel states
- direct `update_provider()` calls update the same provider cache

## Goal

Skip widget tree lookups when deciding whether a Nexus activity frame should
advance.

## Design

- Keep the existing mounted guard.
- Use the current snapshot to detect central running states.
- Use `_provider_state_cache` to detect running provider panels.
- Retain direct-provider-update behavior by relying on the provider cache rather
  than snapshot providers only.
- Let `_apply_activity_frame()` remain responsible for writing the next frame
  when a target exists.

## Tests

- Verify idle snapshots do not query central/provider widgets during
  `advance_activity_frame()`.
- Verify direct provider updates still make `advance_activity_frame()` advance
  even when the snapshot itself is idle.

## Versioning

Patch release: `1.0.261` -> `1.0.262`.
