# Launch CWD Workspace Priority

## Context

Trinity currently seeds the initial target workspace from persisted project
context when that saved target still exists. This is useful when the user
starts Trinity from the control repository and wants to resume the previous
target.

However, it can be surprising when the user launches `trinity` from another
project directory. In that case the launch cwd is an explicit user signal, and
the first screen should not silently switch back to a previously analyzed
project.

## Goal

Prefer the launch cwd as the initial target workspace when it differs from the
control repository path.

## Scope

- Update `initial_workspace_candidate` so a distinct launch cwd wins over
  persisted project context target.
- Keep persisted project context target restore behavior when launching from the
  control repository.
- Add unit coverage for both branches.

## Non-goals

- Do not change workspace picker behavior.
- Do not change persisted project context files.
- Do not change target workspace confirmation logic.
- Do not add migration behavior.

## Expected Behavior

- Launch from control repo: restore saved context target if it still exists.
- Launch from another project path: use that launch path as the initial
  workspace.
- Invalid or unreadable intake: use launch cwd as before.

## Test Plan

- Saved context target exists and launch cwd equals control repo: returns saved
  target.
- Saved context target exists and launch cwd differs from control repo: returns
  launch cwd.
- Invalid intake remains fallback-safe.
