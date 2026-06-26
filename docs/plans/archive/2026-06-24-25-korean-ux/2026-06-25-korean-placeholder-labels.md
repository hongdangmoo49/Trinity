# Korean placeholder labels

Date: 2026-06-25
Branch: ux/korean-placeholder-labels

## Problem

Several Korean Textual report and local-command surfaces already translate their
labels, but still show English placeholder values when data is missing:

- `(none)`
- `(unknown)`
- `(not set)`
- `none` in execution recovery rows

These values are UI helper text, not raw workflow data, so they should follow the
active language.

## Scope

- Add shared presenter helpers for empty, unknown, not-set, and new-session
  placeholders.
- Apply the helpers to execution recovery markdown/rows and snapshot status rows.
- Apply the same convention to Markdown report export placeholders.
- Keep raw workflow states, provider statuses, paths, IDs, and user-authored text unchanged.

## Verification

- Add focused Korean presenter and report export assertions.
- Run focused Textual tests, the Textual app test file, the full test suite, diff
  check, and version check.
