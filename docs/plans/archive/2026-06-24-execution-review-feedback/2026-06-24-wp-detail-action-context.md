# Work Package Detail Action Context

## Problem

The execution matrix now exposes row-level retry, but the work-package detail
modal still reads mostly like a passive spec/result dump. When a package is
failed, blocked, or review-changes-requested, users need the detail view to
answer "what should I do next?" without remembering slash commands.

## Design

- Add an `Action Context` section near the top of the detail modal.
- Use existing `WorkPackageSnapshot` fields only:
  - retryability and retry-disabled reason
  - execution blockers
  - repair blocked reason and attempts
  - review status and required changes
- Keep existing Summary, Result, Review, and Spec sections intact.
- Provide command hints only as plain text context; actual execution remains
  routed through existing execution retry controls.

## Acceptance

- Retryable failed/blocked packages show a direct retry hint.
- Non-retryable packages show why retry is unavailable.
- Review changes requested packages surface required changes in action context.
- Existing detail section ordering remains stable.
