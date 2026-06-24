# Workspace preflight branch placeholder

Date: 2026-06-25
Branch: ux/workspace-preflight-branch-placeholder

## Problem

The workspace preflight modal localizes its labels, but when the target is not a
Git repository the branch value is rendered as the hard-coded English placeholder
`(none)` even in Korean mode.

## Scope

- Localize only the rendered branch placeholder in `WorkspacePreflight.render`.
- Keep `build_preflight` state unchanged so callers still receive the same raw
  branch sentinel.
- Preserve real Git branch names.

## Verification

- Add focused render assertions for Korean and English branch placeholders.
- Run focused Textual tests, the Textual app test file, the full test suite, diff
  check, and version check.
