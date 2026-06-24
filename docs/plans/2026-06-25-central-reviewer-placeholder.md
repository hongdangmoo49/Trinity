# Central reviewer placeholder

Date: 2026-06-25
Branch: ux/central-reviewer-placeholder

## Problem

The central agent panel localizes final review status values, but still renders
the missing reviewer fallback as hard-coded `(unknown)` in Korean mode.

## Scope

- Add a central panel label for the missing reviewer placeholder.
- Use the localized placeholder in final review Markdown.
- Preserve raw reviewer names and status values when present.

## Verification

- Add focused Korean central-agent assertions for the missing reviewer fallback.
- Run focused Textual tests, the Textual app test file, the full test suite, diff
  check, and version check.
