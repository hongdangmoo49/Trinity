# Execute Ack Preflight Visibility

## Context

Workspace preflight already requires a second confirmation before execution when
the selected Git workspace is dirty or project-intake safety warnings exist. The
warning appears after the user presses Confirm Execute once.

The preflight body itself does not explicitly say whether an extra confirmation
will be required. Users can see dirty/intake warning details, but they have to
infer the confirmation behavior.

## Goal

Make the execute acknowledgement requirement visible in the preflight summary.

## Scope

- Add one render line to `WorkspacePreflight.render`.
- Show `required` when dirty Git state or intake safety warnings require a second
  confirm.
- Show `not required` otherwise.
- Add English and Korean labels.
- Cover clean, dirty, and Korean rendering in tests.

## Non-goals

- Do not change the actual acknowledgement gate.
- Do not change dirty Git detection.
- Do not change project-intake safety warning detection.
- Do not alter execution routing.

## Expected Behavior

- Clean workspace: `Execute acknowledgement: not required`.
- Dirty workspace or intake warnings: `Execute acknowledgement: required`.
- Korean UI uses equivalent localized labels.

## Test Plan

- Unit test clean Git preflight renders not required.
- Unit test dirty Git preflight renders required.
- Run required smoke tests before version bump and PR.
