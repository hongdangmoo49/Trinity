# Project Status Scope Choice Guidance

Date: 2026-06-29
Branch: `feature/project-status-scope-choice-guidance`
Status: Superseded by the prompt-led readiness contract. The old
`recommended_action`/`start_trinity` hint has been removed; use
`project_intake.readiness.workbench_next_step`.

## Problem

Start/Nexus now show `choose scope` when an existing-project intake has detected
scope candidates but no confirmed `selected_scope`. The CLI `trinity project
status` used to report the old ready action in this state, and its next steps
did not tell the user how to confirm a scope.

This creates a mismatch between CLI onboarding and Workbench onboarding.

## Proposed UX

When an existing-project intake has `scope_candidates` and no `selected_scope`:

- JSON readiness:
  - `ready: false`
  - `workbench_next_step: "describe_scope"`
  - `scope_choice_required: true`
  - `scope_candidates: [...]`
- Human `Next steps`:
  - `trinity project analyze <target> --scope <scope>`
  - `choose one of: apps/web, packages/core`
  - `trinity`

Target recovery, new-project brief completion, and analysis refresh remain
higher priority.

## Scope

- Update `src/trinity/cli.py` only.
- Keep project intake schema unchanged.
- Do not auto-select scope candidates.
- Keep Workbench behavior unchanged.

## Validation

- Add CLI tests for text and JSON output when scope candidates are present and
  no scope is selected.
- Run:
  - `uv run pytest tests/test_cli.py -q`
  - `uv run python scripts/run_required_smoke_tests.py -q`
