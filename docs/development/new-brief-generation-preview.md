# New Brief Generation Preview

## Problem

Start/Nexus can show a generation preview after a new-project intake is saved,
but the project brief modal itself only shows readiness. While filling the
brief, users cannot see what Trinity currently expects to create or validate
until after saving.

For a new project, that feedback should be visible before the user commits the
brief.

## Goal

Show a compact live generation preview inside the new-project brief modal.

## Scope

- Reuse the existing `format_project_generation_preview_label` formatter so the
  modal and Start/Nexus labels stay consistent.
- Build the preview from the current unsaved draft.
- Update the preview when relevant inputs change.
- Show the preview only when `mode == "new"`.
- Keep save/cancel behavior, project intake persistence, and execution preflight
  unchanged.

## Validation

- Focused Textual tests cover the initial preview and live update after editing
  stack/starter fields.
- Required smoke tests run before PR merge.
