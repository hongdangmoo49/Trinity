# Inspector placeholder labels

Date: 2026-06-25
Branch: ux/inspector-placeholder-labels

## Problem

The workflow inspector already localizes section headings and work-package
summary lines, but some helper values remain English in Korean mode:

- missing workflow ID shows `(new)`
- provider detail labels show `context` and `session`
- missing provider detail values show `default`, `unknown`, and `none`

These are UI helper values and should follow the active UI language.

## Scope

- Add inspector labels for new workflow, default, unknown, context, and session.
- Localize workflow ID fallback and provider detail lines.
- Preserve raw workflow state, provider status, model names, and session IDs.

## Verification

- Add focused Korean inspector assertions for fallback workflow and provider metadata.
- Run focused Textual tests, the Textual app test file, the full test suite, diff
  check, and version check.
