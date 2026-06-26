# Execution Row Retry Action

## Problem

The execution page exposes a global retry action, but retryable failed or
blocked work packages still look like ordinary rows. Users must notice the
global button and then choose the relevant package in the modal.

## Design

- Keep the existing `Spec` / `Blocked` detail action.
- Add a small `Retry` action beside the detail action only for retryable rows.
- Route row retry through the existing execution retry modal with
  `selector=custom` and the clicked WP id preselected.
- Keep non-retryable rows unchanged apart from the action column container.
- Preserve compact status labels and package matrix ordering.

## Acceptance

- Retryable issue rows show a direct retry button.
- Pressing the row retry button opens the existing retry modal with that package
  selected.
- Non-retryable rows do not show a row retry button.
- Existing global retry behavior and detail modal behavior remain unchanged.
