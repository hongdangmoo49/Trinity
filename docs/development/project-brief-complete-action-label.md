# Project Brief Complete Action Label

Date: 2026-06-29
Branch: `feature/project-brief-complete-action-label`

## Problem

Start and Nexus already highlight `Edit Brief` with a warning variant when a
saved new-project intake is missing required brief fields. The color helps, but
the label still sounds optional. A new-project user may not realize that the
brief is the next recommended step before planning and execution.

## Proposed UX

Use a dynamic brief button label:

- Incomplete new-project brief: `Complete Brief`
- Otherwise: `Edit Brief`

Korean:

- Incomplete new-project brief: `브리프 완성`
- Otherwise: `브리프 편집`

This mirrors the existing warning variant and keeps the button placement and
message routing unchanged.

## Scope

- Add a pure presenter helper for the brief action label key.
- Reuse the same target/intake checks as `project_brief_action_variant()`.
- Update Start and Nexus compose/refresh paths to set the dynamic label.
- Keep existing modal behavior unchanged.

## Validation

- Add focused presenter tests for incomplete, complete, and mismatched targets.
- Add Start/Nexus screen tests showing the button label refreshes with intake
  state.
- Run:
  - `uv run pytest tests/test_start_screen.py -q`
  - `uv run python scripts/run_required_smoke_tests.py -q`
