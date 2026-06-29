# Existing Read-First Preview

## Problem

Existing-project analysis asks providers to read detected docs and source roots
before proposing work. The analysis-anchor review modal lets users edit those
anchors, but it does not show the derived `read first` set that will appear in
the seeded analysis prompt.

For existing projects, this leaves one important question slightly implicit:
"What will Trinity ask agents to inspect first?"

## Goal

Show a compact live `read first` preview inside the existing-project anchor
review modal.

## Scope

- Derive the preview from `docs_found + source_roots`.
- Update the preview when the docs or source roots fields change.
- Keep saved project intake, prompt generation, and execution preflight behavior
  unchanged.
- Do not add provider calls or filesystem reads during modal editing.

## Validation

- Focused Textual tests cover the initial preview and live update after editing
  docs/source roots.
- Required smoke tests run before PR merge.
