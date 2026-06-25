# Agent Selector Toggle Cache

## Context

`AgentRecipientModelSelector` creates one stable `AgentToggle` widget per agent
when composing the start and Nexus recipient selectors. Selection reads and
restores currently use `query_one("#recipient-{name}")` for every agent.

These selectors are touched during prompt submission, restored start-to-Nexus
state, and follow-up commands. The toggle widgets are stable for the selector
lifetime, so repeated DOM lookups are unnecessary.

## Goal

Avoid repeated selector queries for agent toggles after the widgets are
composed.

## Design

- Cache `AgentToggle` instances by agent name when composing the selector.
- Route `selected_agents()` and `set_selected_agents()` through a helper that
  uses the cache.
- Keep a query fallback in the helper so tests or unusual construction paths
  still behave like the existing implementation.

## Tests

- Add a focused selector cache test.
- Verify selected-agent reads and programmatic selection updates do not call
  `query_one()` for recipient toggles once the selector is mounted.
- Keep existing model choice cache tests intact.

## Versioning

Patch release: `1.0.266` -> `1.0.267`.
