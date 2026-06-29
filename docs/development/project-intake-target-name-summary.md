# Project Intake Target Name Summary

Date: 2026-06-29
Branch: `feature/project-intake-target-name-summary`

## Problem

Start and Nexus already display the selected target workspace separately from
the saved project intake summary. The intake summary says whether the mode is
`new` or `existing`, when it was updated, tests, Git state, source roots, and
brief fields.

However, users still need to compare labels mentally to confirm which project
the saved intake belongs to. This is especially awkward when:

- Trinity was launched from a control workspace.
- The target workspace was changed after analysis.
- A user starts from an existing project and wants confidence that agents are
  discussing that repository.
- A new-project user creates multiple similarly named folders.

## Proposed UX

Add a compact target name segment near the front of the saved project intake
summary:

```text
Project intake: existing | target: customer-app | updated: 2026-06-28 | ...
```

Korean:

```text
프로젝트 인테이크: 기존 | 대상: customer-app | 갱신: 2026-06-28 | ...
```

Use the final path name for readability. If the path has no name, use the
resolved target path string.

## Scope

- Update `format_project_intake_label()` through its existing internal helper.
- Keep missing-intake and invalid-intake labels unchanged.
- Do not change target mismatch or target missing semantics.
- Keep the full target path visible in the dedicated workspace label.

## Validation

- Update focused Start/Nexus presenter tests that assert project-intake summary
  strings.
- Run:
  - `uv run pytest tests/test_start_screen.py -q`
  - `uv run python scripts/run_required_smoke_tests.py -q`
