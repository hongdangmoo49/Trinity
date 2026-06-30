# Project Context Refresh On Target Change

Date: 2026-06-29
Branch: `feature/project-context-refresh-on-target-change`

## Problem

This note predates the prompt-led Workbench simplification. At that point Start
and Nexus exposed several project-context surfaces:

- workspace label
- startup readiness
- saved project context summary
- plan/generation/validation previews
- read-first checklist
- analyze/create/brief action state

The current Start and Nexus screens no longer mount those persistent project
context labels or setup actions. They keep the workspace label visible and let
`/project` diagnostics, CLI status, execution preflight, and provider prompt
guidance compute project context on demand.

For new-project onboarding, this avoids showing the wrong brief/generation
guidance after a target switch. For existing-project onboarding, it avoids
showing stale analysis, scope, or read-first guidance as always-visible chrome.

## Proposed UX

Whenever the effective target workspace changes:

- refresh the visible workspace label;
- leave project-context details to `/project` diagnostics and execution
  preflight;
- avoid extra work when a Nexus fallback workspace changes but an active
  workflow snapshot target still owns the effective target.

## Scope

- Wire Start `set_workspace_candidate()` to use the existing workspace label
  refresh.
- Wire Nexus `set_workspace_candidate()` and `apply_snapshot()` to refresh the
  workspace label when the effective target changes.
- Keep project diagnostics and saved project context semantics unchanged.

## Validation

- Add focused Start/Nexus widget tests for workspace label refresh.
- Run:
  - `uv run pytest tests/test_start_screen.py tests/test_textual_app.py -q`
  - `uv run python scripts/run_required_smoke_tests.py -q`
