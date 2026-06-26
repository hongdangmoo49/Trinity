# Context presenter placeholder i18n

Date: 2026-06-25
Branch: ux/context-presenter-placeholders

## Problem

`/context` Markdown uses Korean section labels, but a few fallback values still
come from hard-coded English placeholders:

- `(new)` for missing workflow IDs
- `(none)` for missing goals
- `(unnamed)`, `(no package)`, and `(unknown)` for incomplete subtask metadata

These are UI helper values and should follow the active UI language.

## Scope

- Reuse the existing presenter placeholder helpers inside `snapshot_context_markdown`.
- Keep raw workflow state, question status, package text, agent names, and user-authored text unchanged.
- Keep the no-current-context message behavior unchanged.

## Verification

- Add focused Korean context Markdown assertions for missing workflow, goal, and subtask metadata.
- Run focused Textual tests, the Textual app test file, the full test suite, diff
  check, and version check.
