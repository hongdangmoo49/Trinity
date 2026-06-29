# Startup Readiness Checklist

## Goal

When a user starts Trinity on a new or existing project, the Start and Nexus
screens should answer one immediate question: "Can I safely start planning or
execution from this state?"

The current workbench already exposes detailed target, project intake,
provider policy, validation plan, read-first, and generation previews. The
readiness checklist is a compact rollup above those details.

## User Cases

- New project: show whether a target folder is selected, the project brief is
  usable, providers are selected, and validation is planned.
- Existing project: show whether a target folder is selected, project intake is
  usable for that target, providers are selected, and validation is planned.
- Partial setup: keep the line useful when only one provider is enabled or when
  no project intake has been recorded yet.

## UI Contract

Render one concise line on Start and Nexus:

```text
Startup readiness: target ok | intake ok | providers 2 | validation planned
```

Localized Korean copy:

```text
시작 준비: 대상 정상 | 인테이크 정상 | 프로바이더 2개 | 검증 계획됨
```

The line is intentionally status-only. Detailed next actions remain in the
existing mode rail and project intake labels.

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

- Put the rollup logic in `trinity.textual_app.workspace_labels` so Start and
  Nexus share the same decisions.
- Reuse existing intake and validation helper functions instead of adding a
  second project-state model.
- Refresh the label when project intake, target workspace, or selected providers
  change.

## Test Plan

- Unit-test the readiness label for missing, ready new-project, and existing
  project states.
- Render-test Start and Nexus to confirm the new static label appears.
- Verify provider selection updates the provider count in the readiness line.
