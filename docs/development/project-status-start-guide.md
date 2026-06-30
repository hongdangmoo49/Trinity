# Project Status Start Guide

Date: 2026-06-29
Branch: `feature/project-status-start-guide`
Status: Superseded by the simplified Workbench flow. Project status no longer
mirrors Workbench `Analyze Existing` / `Create New` button guidance, and the
legacy `project_start_guide` JSON field has been removed in favor of
`project_intake.readiness.workbench_next_step`.

## Problem

Start and Nexus now show a compact `Project start` guide that explains the two
onboarding paths:

- existing project -> analyze existing
- new project -> create new

CLI users still rely on `trinity project status` for the same readiness facts,
but the status output does not surface that project-start guide. This creates a
small mismatch between CLI onboarding and Workbench onboarding.

## Proposed UX

Add the same guide to `trinity project status`:

```text
Start guide: Project start: existing -> Analyze Existing | new -> Create New | then Plan first
```

When intake exists:

```text
Start guide: Project start: mode existing | next -> Analyze Existing | then Plan first
```

This JSON field is no longer part of the current status contract. Consumers
should use `project_intake.readiness.workbench_next_step` instead.

## Scope

- The old `project_start_choice_guide_label(...)` helper has been removed.
- Add the guide to human `project status` output.
- Add the guide to `project status --json` when project intake exists.
- Keep next-step commands unchanged.

## Validation

- Update focused CLI tests.
- Run:
  - `uv run pytest tests/test_cli.py -q`
  - `uv run python scripts/run_required_smoke_tests.py -q`
