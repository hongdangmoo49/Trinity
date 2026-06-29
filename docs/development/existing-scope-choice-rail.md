# Existing Scope Choice Rail

Date: 2026-06-29
Branch: `feature/existing-scope-choice-rail`

## Problem

Existing-project scope candidates are now shown as an explicit choice in the
project intake summary and read-first checklist. The start-flow rail can still
show the project as ready when analysis is fresh and scope candidates exist but
`selected_scope` is empty.

In a monorepo, that makes the top-level readiness signal weaker than the
detailed labels below it.

## Proposed UX

When an existing-project intake has `scope_candidates` and no `selected_scope`,
show the rail as:

```text
Start flow: target: ready -> intake: scope needed -> plan: caution -> execute: confirm | mode: existing | next: choose scope
```

Korean:

```text
시작 흐름: 대상: 준비됨 -> 인테이크: 범위 필요 -> 계획: 주의 -> 실행: 확인 필요 | 모드: 기존 | 다음: 범위 선택
```

Startup readiness should also move from `intake ok` to `intake check` in this
state.

## Scope

- Update `project_mode_rail_label()`.
- Update `project_startup_readiness_label()` through its intake-key helper.
- Keep execution behavior unchanged; this is a visibility hint, not a blocker.
- Do not auto-select scope candidates.

## Validation

- Add focused tests in `tests/test_start_screen.py` for English and Korean rail
  output.
- Verify startup readiness reports `intake check`.
- Run:
  - `uv run pytest tests/test_start_screen.py -q`
  - `uv run python scripts/run_required_smoke_tests.py -q`
