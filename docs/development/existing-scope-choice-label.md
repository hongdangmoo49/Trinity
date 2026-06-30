# Existing Scope Choice Label

Date: 2026-06-29
Branch: `feature/existing-scope-choice-label`

## Problem

Existing-project intake can detect scope candidates such as `apps/web` or
`packages/core`, and it can persist a user-confirmed `selected_scope`.

When `selected_scope` is empty, project diagnostics and CLI status can show
detected candidates as plain `scopes: apps/web, packages/core`. This is useful,
but it does not clearly tell the user that the scope has not been confirmed yet.
In monorepos, that ambiguity can make agents analyze or plan too broadly.

## Proposed UX

When an existing-project intake has scope candidates but no selected scope,
show an action-oriented segment:

```text
choose scope: apps/web, packages/core
```

Korean:

```text
범위 선택: apps/web, packages/core
```

When `selected_scope` exists, keep the existing confirmed form:

```text
scope: apps/web
scopes: apps/web, packages/core
```

## Scope

- Update the project intake diagnostic/summary label only.
- Keep project intake schema unchanged.
- Keep prompt guidance unchanged; it already tells providers to ask before broad
  edits when only candidates are available.
- Do not auto-select scope candidates.

## Validation

- Update project-intake label coverage for scope candidates with and without
  `selected_scope`.
- Run:
  - `uv run pytest tests/test_start_screen.py -q`
  - `uv run python scripts/run_required_smoke_tests.py -q`
