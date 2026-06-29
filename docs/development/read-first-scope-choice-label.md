# Read-First Scope Choice Label

Date: 2026-06-29
Branch: `feature/read-first-scope-choice-label`

## Problem

The project intake summary now distinguishes detected scope candidates from a
confirmed `selected_scope` by showing `choose scope`. The read-first checklist
still renders unconfirmed candidates as plain scope values:

```text
Read-first checklist: scope: apps/web, packages/core | ...
```

For existing-project users, especially in monorepos, the checklist should also
make it clear that these are candidates to choose from before broad edits.

## Proposed UX

When `selected_scope` is present:

```text
Read-first checklist: scope: apps/web | ...
```

When only `scope_candidates` exist:

```text
Read-first checklist: scope: choose apps/web, packages/core | ...
```

Korean:

```text
먼저 읽기 체크리스트: 범위: 선택 apps/web, packages/core | ...
```

## Scope

- Update only the read-first checklist label presenter.
- Keep target-root fallback unchanged.
- Keep project intake schema and prompt injection unchanged.

## Validation

- Add focused `tests/test_start_screen.py` coverage for unconfirmed scope
  candidates.
- Run:
  - `uv run pytest tests/test_start_screen.py -q`
  - `uv run python scripts/run_required_smoke_tests.py -q`
