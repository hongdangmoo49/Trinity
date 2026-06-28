# Workbench Analyze Action Presentation

This design reduces duplicated Workbench project-intake analysis work introduced
by the dynamic `Refresh Analysis` label.

## Problem

Start/Nexus need two values for the existing-project analyze action:

- the button label key;
- the button variant.

Both values depend on the same saved project-intake state and the same live
read-only drift check. Calling separate helpers can repeat the filesystem/Git
inspection needed to decide whether the intake is sparse, stale, or changed.

## Contract

Add one shared presentation helper that returns both values from a single
readiness decision:

- `label_key`: `analyze_workspace` or `refresh_analysis`
- `variant`: `default` or `warning`

Start/Nexus should use the presentation helper during compose and refresh.
Existing public helpers for variant and label key remain available for tests and
callers, but they delegate to the shared presentation decision.

## Scope

This is a render-cost cleanup. It must not change:

- action ids;
- event flow;
- project-intake persistence;
- stale/sparse/changed detection rules;
- Korean or English user-facing wording.

## Tests

Coverage should prove:

- the presentation helper returns the existing label/variant for normal intake;
- sparse, stale, or changed matching existing intake returns
  `refresh_analysis` and `warning`;
- Start/Nexus mounted buttons still update label and variant after intake state
  changes.
