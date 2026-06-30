# Project Status Missing Start Guide

Date: 2026-06-29
Branch: `feature/project-status-missing-start-guide`
Status: Superseded by the simplified Workbench flow. Status output no longer
needs to mirror Workbench existing/new action buttons; prompt-led guidance is
the current Workbench model.

## Problem

`trinity project status` now shows a `Start guide` when project intake exists.
The missing-intake state is still the first status many CLI users see, but it
only lists commands separately:

- existing project analyze command
- new project command
- run `trinity`

That is useful but less consistent with Start/Nexus and the populated status
output, which now use a single `Project start` guide line.

## Proposed UX

For human output, add the same start guide:

```text
Start guide:
  Project start: existing -> Analyze Existing | new -> Create New | then Plan first
```

For JSON output, add a top-level `project_start_guide` field even when
`project_intake` is `null`.

## Scope

- Reuse `project_start_choice_guide_label(...)` for missing-intake status.
- Keep existing command next steps unchanged.
- Keep populated-intake JSON shape from the previous PR unchanged.

## Validation

- Update focused CLI tests for human and JSON missing-intake status.
- Run:
  - `uv run pytest tests/test_cli.py -q`
  - `uv run python scripts/run_required_smoke_tests.py -q`
