# Report screen Korean labels

Date: 2026-06-24
Branch: ux/report-screen-korean-labels

## Problem

The `/report` command and export notifications are localized, but the interactive
Report screen still renders many section titles and summary labels in English.
Korean users see a mixed-language report even when the app language is set to
`ko`.

## Scope

- Localize the Report screen section titles.
- Localize the first-level overview labels and common report summary terms.
- Localize snapshot fallback provider, routing, quality, recovery, and question
  labels that are shown directly in the screen body.
- Keep raw workflow values, provider names, statuses, package IDs, and user text
  unchanged.
- Leave Markdown export format untouched because it is already handled through
  the report export path.

## Verification

- Add a Korean Report screen snapshot test that asserts localized section titles
  and body labels.
- Run focused Report screen tests, Textual app tests, full test suite, diff check,
  and version check.
