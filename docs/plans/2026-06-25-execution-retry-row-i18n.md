# Execution retry row i18n

Date: 2026-06-25
Branch: ux/execution-retry-row-i18n

## Problem

The execution retry modal already localizes its title, filters, headers, buttons,
and status cells. However, row metadata still contains English helper labels in
Korean mode:

- fallback executor indicator: `fallback`
- repair attempt note: `repair 2/3`

This leaves a small mixed-language artifact in the retry picker.

## Scope

- Localize retry row executor fallback suffix.
- Localize retry row repair attempt prefix.
- Keep package IDs, agent names, raw retry-disabled reasons, and repair reasons unchanged.
- Preserve English output by default for existing tests and diagnostics.

## Verification

- Add focused helper and modal tests for Korean row labels.
- Run focused retry tests, Textual app tests, full test suite, diff check, and version check.
