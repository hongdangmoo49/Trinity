# Existing Context Drift Preflight

This design covers the next saved project context safety improvement for
existing projects. It focuses on users who analyze a project, keep working, then
execute later from Nexus or Start.

## Problem

Saved existing-project context is a point-in-time read-only profile. It records
Git state, package managers, test/dev/build commands, entrypoints, source roots,
and docs found. That profile can become misleading even when it is not old
enough to be considered stale:

- the user changes branch after analysis;
- the Git dirty or untracked count changes after analysis;
- package/test/source/doc anchors are added or removed after analysis.

If Trinity executes against this changed workspace without surfacing the drift,
agents may plan from outdated assumptions.

## User Contract

During execute preflight, when the saved existing-project context target matches
the selected workspace, Trinity compares the saved profile to a fresh read-only
profile.

If any meaningful profile signal differs, preflight adds
`changed_project_intake`. The first `Confirm Execute` keeps the modal open and
shows the safety warning. A second `Confirm Execute` proceeds explicitly.

Workspace selection remains read-only and ungated. The user can still select or
analyze a workspace without passing an execution gate.

## Drift Signals

The first implementation checks only cheap, deterministic signals already used
by the saved project context profile:

- Git repository flag, branch, dirty count, and untracked count.
- Package managers.
- Test commands.
- Development commands.
- Build commands.
- Entrypoints.
- Source roots.
- Documentation anchors.

The check must not execute package managers, tests, build tools, or user code.
It may call `git status --porcelain`, matching existing preflight behavior.

## Non-Goals

- Automatically refreshing the saved context during execute.
- Blocking execution outright.
- Semantic project classification.
- Provider prompt changes.
- A separate refresh button in the preflight modal.

Those can be added later after the warning contract is stable.

## Tests

Coverage should prove:

- unchanged saved existing-project context is not gated;
- changed Git state is reported as `changed_project_intake`;
- changed analysis anchors are reported as `changed_project_intake`;
- Textual execute mode requires a second confirmation for this warning;
- select mode continues to skip execution gates.
