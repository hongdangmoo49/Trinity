# Execution matrix fallback label

Date: 2026-06-25
Branch: ux/execution-matrix-fallback-label

## Problem

The execution matrix localizes its chrome and review labels, but fallback
executor rows still render the English suffix `fallback` in Korean mode.

## Scope

- Localize the fallback executor suffix in execution matrix rows.
- Preserve raw executor and owner agent names.
- Keep English output unchanged.

## Verification

- Add focused Korean execution matrix assertions for fallback executor rows.
- Run focused Textual tests, the Textual app test file, the full test suite, diff
  check, and version check.
