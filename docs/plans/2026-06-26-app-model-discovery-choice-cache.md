# App Model Discovery Choice Cache

## Context

Provider model discovery reports model choices one agent at a time. Start and
Nexus screens already skip unchanged choices in `set_agent_model_choices()`, but
`TrinityTextualApp._apply_discovered_model_choices()` still forwards duplicate
choice payloads to every mounted screen and the model settings modal.

The app shell can filter unchanged agent choices before touching UI surfaces.

## Goal

Avoid screen/modal synchronization calls when discovered model choices have not
changed at the app level.

## Design

- Normalize incoming choices to tuples per agent.
- Compare each tuple with `_agent_model_choices`.
- Store and forward only changed agent entries.
- Return early when the incoming payload is entirely unchanged.
- Preserve late model settings modal behavior by forwarding changed entries to
  the modal when it is open.

## Tests

- Add an app-level model discovery cache test.
- Verify duplicate discovered choices do not call Start or Nexus screen sync
  methods.
- Verify changed choices still propagate to both screens.

## Versioning

Patch release: `1.0.257` -> `1.0.258`.
