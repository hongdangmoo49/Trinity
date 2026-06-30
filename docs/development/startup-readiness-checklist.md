# Project Diagnostic Readiness Checklist

## Goal

When a user asks for project diagnostics, Trinity should answer one immediate
question: "Can I safely start planning or execution from this state?"

The current Workbench keeps Start/Nexus chrome small: workspace selection stays
visible, and detailed target, project intake, validation, read-first, and
generation previews live in `/project` diagnostics and CLI status. The readiness
checklist is a compact rollup for those diagnostic surfaces.

## User Cases

- New project: show whether a target folder is selected, the project brief is
  usable, providers are selected, and validation is planned.
- Existing project: show whether a target folder is selected, project intake is
  usable for that target, providers are selected, and validation is planned.
- Partial setup: keep the line useful when only one provider is enabled or when
  no project intake has been recorded yet.

## Diagnostic Contract

Render one concise line in `/project` diagnostics:

```text
Readiness: target ok | context ok | providers 2 selected | validation planned
```

Localized Korean copy:

```text
준비 상태: 대상 정상 | 컨텍스트 정상 | 프로바이더 2개 선택 | 검증 계획됨
```

The line is intentionally status-only. Detailed next-action context remains in
project diagnostics, CLI status, and the user's prompt.

## State Rules

- Target is `ok` when a non-empty workspace target is selected.
- Intake is `missing` when there is no saved intake.
- Intake is `check` when intake is unreadable, target-mismatched, target-missing,
  incomplete for a new-project brief, sparse/stale/changed for an existing
  project analysis.
- Providers show the count of active selected providers, falling back to all
  enabled providers before the selector is mounted.
- Validation is `planned` when the existing validation plan helper can render a
  plan for the current target.

## Implementation Notes

- Put the rollup logic in `trinity.textual_app.workspace_labels` so Textual
  diagnostics can share the same decisions.
- Reuse existing intake and validation helper functions instead of adding a
  second project-state model.
- Compute the label on demand when `/project` diagnostics are requested.

## Test Plan

- Unit-test the readiness label for missing, ready new-project, and existing
  project states.
- Verify `/project` diagnostics include the readiness line.
- Verify provider selection updates the provider count in the readiness line.
