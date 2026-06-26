# Screen Model Choice Delta Apply

## Context

Start and Nexus screens cache discovered model choices and skip unchanged agent
entries in `set_agent_model_choices()`. When at least one agent changes, both
screens call `_apply_model_choices()`, which currently forwards every cached
agent choice to `AgentRecipientModelSelector`.

After app-level discovery filtering, incoming payloads are already deltas. The
screens should preserve that narrow shape instead of expanding a one-agent
change into all cached agents.

## Goal

Apply only changed model choice entries during live discovery updates, while
still applying the full cache during screen mount.

## Design

- Collect `changed_choices` in `set_agent_model_choices()`.
- Let `_apply_model_choices()` accept an optional `choices_by_agent` argument.
- On mount, call `_apply_model_choices()` without an argument to apply the full
  screen cache.
- During live updates, call `_apply_model_choices(changed_choices)` so the
  selector receives only changed agents.

## Tests

- Extend agent model choice cache tests for Start and Nexus.
- Seed each screen with multiple agents.
- Change only one agent and assert the selector receives only that changed
  agent.

## Versioning

Patch release: `1.0.258` -> `1.0.259`.
