# Project Start Flow Rail

Date: 2026-06-29
Branch: `feature/project-start-flow-rail`

## Problem

Start and Nexus already show target workspace, provider setup, project intake,
plan preview, generation preview, validation plan, and read-first checklist.
The information is useful, but a first-time user has to infer the order:

1. choose or create the target workspace
2. analyze existing code or complete a new-project brief
3. start planning
4. execute only when the target and intake are safe

The current `Mode rail` label compresses this into `mode`, `state`, and `next`.
That is concise, but it does not make the journey visible for new-project and
existing-project users.

## User Outcomes

### New Project

- User can see that target selection and brief completion come before planning.
- If the brief is incomplete, planning remains visually conditional on editing
  the brief.
- When the brief is complete, the rail says planning and execution are ready.

### Existing Project

- User can see whether the target workspace analysis is ready, stale, sparse,
  changed, or mismatched.
- If analysis needs refresh, planning is shown as caution and execution as a
  confirm-only step rather than a smooth green path.
- Target mismatch remains the highest-priority state because it can cause agents
  to talk about the wrong project.

## Proposed Surface

Keep the existing presenter function and widget placement:

- `project_mode_rail_label(...)`
- Start widget id: `project-mode-rail`
- Nexus widget id: `nexus-project-mode-rail`

Change the text from a single state label into a four-step rail:

```text
Start flow: target: ready -> intake: ready -> plan: ready -> execute: ready | mode: new | next: plan or execute
```

Korean:

```text
시작 흐름: 대상: 준비됨 -> 인테이크: 준비됨 -> 계획: 준비됨 -> 실행: 준비됨 | 모드: 신규 | 다음: 계획 또는 실행
```

## Scope

- Update `PROJECT_MODE_RAIL_LABELS` to stage-oriented labels.
- Update `project_mode_rail_label` to derive target, intake, plan, and execute
  stage labels from the same existing readiness checks.
- Keep all checks read-only.
- Do not change button layout or workflow state transitions in this slice.

## Validation

- Update focused presenter tests in `tests/test_start_screen.py`.
- Update any Textual integration assertions that render the project rail.
- Run:
  - `uv run pytest tests/test_start_screen.py tests/test_textual_app.py -q`
  - `uv run python scripts/run_required_smoke_tests.py -q`
