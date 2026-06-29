# Project Context Refresh On Target Change

Date: 2026-06-29
Branch: `feature/project-context-refresh-on-target-change`

## Problem

Start and Nexus expose several project-context surfaces:

- workspace label
- startup readiness
- project intake summary
- start flow rail
- plan/generation/validation previews
- read-first checklist
- analyze/create/brief action state

The screens already have `refresh_project_intake_summary()` helpers that update
these surfaces together. However, changing the selected target workspace only
refreshes the workspace label and startup readiness in some paths. That can
leave stale project guidance visible after a user switches from one project to
another.

For new-project onboarding this can show the wrong brief/generation guidance.
For existing-project onboarding this can show the wrong analysis, scope, or
read-first guidance.

## Proposed UX

Whenever the effective target workspace changes:

- refresh the visible workspace label;
- refresh all project-context labels and action variants from the same target;
- avoid extra work when a Nexus fallback workspace changes but an active
  workflow snapshot target still owns the effective target.

## Scope

- Wire Start `set_workspace_candidate()` to use the existing full project
  context refresh.
- Wire Nexus `set_workspace_candidate()` and `apply_snapshot()` to refresh the
  full project context when the effective target changes.
- Keep label wording and project intake semantics unchanged.

## Validation

- Add focused Start/Nexus widget tests for target change refresh.
- Run:
  - `uv run pytest tests/test_start_screen.py tests/test_textual_app.py -q`
  - `uv run python scripts/run_required_smoke_tests.py -q`
