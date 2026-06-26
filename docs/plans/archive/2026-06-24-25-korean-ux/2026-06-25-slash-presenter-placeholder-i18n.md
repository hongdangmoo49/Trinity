# Slash presenter placeholder i18n

Date: 2026-06-25
Branch: ux/slash-presenter-placeholders

## Problem

Korean slash-command presenters still expose a few English placeholder values in
summary rows and Markdown:

- `(new)` for missing workflow IDs
- `(none)` for empty goals, review lists, action items, and summaries
- `(unknown)` for missing reviewers and delegated agents
- `(no package)` and `(unnamed)` in subtask output

This is the same class of helper text as the report placeholder cleanup, but it
appears in other local command presenters.

## Scope

- Reuse the shared presenter placeholder helpers for workflow/report/review/improve/history/resume rows.
- Add subtask-specific helper labels for unnamed subtasks and missing parent packages.
- Preserve raw workflow states, statuses, IDs, agent names, user-authored text, and command summaries.
- Keep English output unchanged.

## Verification

- Add focused Korean assertions for report/workflow/review/improve/subtask/history/resume placeholders.
- Run focused Textual tests, the Textual app test file, the full test suite, diff
  check, and version check.
