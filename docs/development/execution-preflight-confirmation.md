# Execution Preflight Confirmation

## Background

After planning, Nexus can move directly into execution. Trinity now shows the selected
workspace and project intake state more clearly, but the final "execute" action still
has a high cost: agents may start writing files in the selected target immediately.

Users starting either a new project or an existing project need one last confirmation
that the execution target, project mode, active providers, and work packages match
their intent.

## Goal

- Add a confirmation modal before Nexus starts execution.
- Show the target workspace, project intake mode, selected/active providers, and work
  package summary.
- Keep the existing missing-target workspace picker flow.
- Keep execution retry and repair retry flows unchanged.
- Route Nexus `/execute` through the same confirmation path where possible.

## User Experience

When the user presses Execute from Nexus, Trinity should show:

```text
Confirm Execution
Target workspace: /home/user/workspace/msu
Project mode: existing
Providers: claude, codex
Work packages: 3 total, 3 executable
Preview:
- WP-001 codex Build API client
- WP-002 claude Update docs
```

The user can cancel or confirm. Only confirm calls the existing
`workflow_controller.request_execution()` path.

## Non-goals

- Do not change the workflow engine execution state machine.
- Do not change retry selection modals.
- Do not block execution for missing optional project intake fields.

## Validation

- Unit tests for modal summary formatting.
- App tests proving Execute does not call the controller until confirm.
- App tests proving cancel leaves execution untouched.
- Existing missing target and `/execute` error tests remain covered.
- Required smoke tests before merge.
