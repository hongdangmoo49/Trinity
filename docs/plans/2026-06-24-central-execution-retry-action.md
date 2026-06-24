# Central Execution Retry Action

## Problem

Execution recovery can expose retry candidates after failed, blocked, or
interrupted work packages. The Execution Matrix has a retry button, but the
central Nexus panel does not surface a first-class action for normal execution
recovery. Users may see an execution failure in the central flow and not notice
that retry is available elsewhere.

## Design

- Show a central action when `execution_recovery.retry_candidates` is not empty.
- Route the central action through the existing `/execute-retry all` command.
- Keep provider error gate and review repair gate actions higher priority.
- Do not show retry for review-repair blocked states because those already have
  dedicated repair actions.

## Acceptance

- A snapshot with retry candidates renders a central retry action.
- Pressing the action opens the existing execution retry modal.
- Existing provider-error and repair actions continue to take precedence.
