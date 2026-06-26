# Report screen fallback placeholder i18n

Date: 2026-06-25
Branch: ux/report-screen-fallback-placeholders

## Problem

`ReportScreen` already localizes section and field labels, but the fallback
snapshot renderer still exposes a few English helper values in Korean mode:

- `serial` for non-parallel work package lanes
- `reason` in skipped review summaries
- `(none)` from empty execution event, review, and conversation sections
- `(unknown)` for missing advisory quality agent names
- raw `unknown` for missing provider implementation names

These values are UI helper text, not workflow-authored content.

## Scope

- Localize fallback helper values in `src/trinity/textual_app/screens/report.py`.
- Preserve raw workflow statuses, provider names, model labels, package IDs, paths,
  and user-authored summaries.
- Keep English output unchanged.

## Verification

- Add focused Korean report-screen assertions for localized placeholders and lane/review labels.
- Run focused Textual tests, the Textual app test file, the full test suite, diff
  check, and version check.
