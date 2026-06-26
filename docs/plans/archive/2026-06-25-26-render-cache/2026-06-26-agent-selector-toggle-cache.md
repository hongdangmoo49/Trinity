# Agent Selector Toggle Cache

## Context

`AgentRecipientModelSelector` is shared by the Start and Nexus screens. It keeps
an `_toggle_cache` and seeds it while composing agent toggles, so selected-agent
reads and updates can avoid repeated selector lookups. The cache is not reset at
the start of compose, which makes future recomposition less explicit than the
other recently optimized widgets.

## Goal

Make the selector toggle cache compose-scoped and verify common selection paths
reuse composed toggles without selector lookups.

## Design

- Reset `_toggle_cache` before composing selector toggles.
- Keep caching every `AgentToggle` by agent name during compose.
- Preserve the existing `_toggle_for()` query fallback for unusual cases.
- Keep model choice and model selection behavior unchanged.

## Tests

- Add a focused selector test verifying `set_selected_agents()`,
  `selected_agents()`, and `model_overrides()` reuse composed toggle widgets
  without `query_one()`.
- Keep Nexus agent selection cache tests intact.

## Versioning

Patch release: `1.0.281` -> `1.0.282`.
