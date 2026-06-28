# Project Brief Placeholders

## Problem

The project brief modal asks for product goal, type, users, success criteria,
stack, milestone, constraints, and notes. The labels are accurate, but first-run
users still need to infer the expected level of detail. This is especially true
when starting a new project from an empty workspace.

## Scope

- Add short localized placeholders to project brief inputs.
- Keep all fields optional from the modal perspective.
- Do not change project-intake persistence, readiness policy, preflight gates,
  or prompt generation.
- Keep existing saved draft values taking priority over placeholders.

## Design

Extend `PROJECT_BRIEF_LABELS` with placeholder keys and pass the placeholder to
Textual `Input`. The modal continues to use the same field ids and save logic.

Placeholders should be examples, not instructions:

- Product goal: a concrete outcome.
- Project type: product category.
- Target users: audience or role.
- Success criteria: observable first success.
- Stack preferences: comma-separated technologies.
- First milestone: first shippable result.
- Constraints: comma-separated boundaries.
- Notes: optional extra context.

## Tests

- English modal inputs expose the expected placeholders.
- Korean modal inputs expose localized placeholders.
- Existing draft values remain visible in the inputs.
