# Nexus Brief Follow-Up Prompt

Status: Superseded by the simplified Workbench flow. Nexus no longer exposes
`Edit Brief` or project brief save handlers; users express product intent in the
follow-up prompt.

## Problem

The project brief modal can be opened from Nexus. After saving the brief,
Trinity writes project intake and seeds the Start composer, but the user is
still looking at Nexus. The Nexus follow-up composer can remain empty even
though the user just provided enough brief context to continue.

This is visible in the new-project path: `Create Project` opens the brief modal
from Nexus, then returns to a blank Nexus composer after save.

## Goals

- When the active route is Nexus and the user saves a project brief, seed the
  Nexus follow-up composer with the same brief-based prompt used by Start.
- Only seed the Nexus composer when it is empty.
- Keep Start prompt seeding unchanged.
- Avoid pre-filling Nexus while the user is on Start, because that can create a
  stale follow-up after the Start prompt is submitted.
- Preserve the current target-workspace check before writing into a composer.

## Non-Goals

- Do not auto-submit the follow-up.
- Do not change Nexus follow-up routing or agent recipient selection.
- Do not change project-intake schema or provider prompt injection.

## Design

1. Reuse the existing project-brief prompt builder.
2. After project brief save, attempt Start seeding as before.
3. If `current_route == "nexus"`, the Nexus screen is mounted, the selected
   target still matches the saved brief target, and the Nexus composer is
   empty, seed the Nexus composer.
4. If the user already typed a follow-up, leave it untouched.

## Tests

- Nexus `Edit Brief` save seeds `#nexus-composer` with the brief prompt.
- Existing Start brief tests continue to prove Start prompt behavior.
