# Existing Scope Preflight Label

## Problem

Existing-project intake can now persist a `selected_scope`, and the analysis
prompt includes that scope. However, the Execute Preflight modal still shows the
target workspace only at repository level. For monorepo users, this makes the
last confirmation before execution less explicit than the earlier analysis
step.

## Goal

Show the saved selected scope in Execute Preflight when the current target
workspace matches the saved existing-project intake.

## Scope

- Add an optional scope label to `WorkspacePreflight`.
- Populate it from `project-intake.json` only when:
  - intake exists and is readable,
  - intake mode is `existing`,
  - intake target matches the preflight target,
  - `selected_scope` is non-empty.
- Render the scope in English and Korean preflight output.
- Keep execution permissions, safety warnings, and prompt contracts unchanged.

## Validation

- Workspace picker unit tests cover matching selected scope, target mismatch,
  and new-project intake not rendering a scope label.
- Required smoke tests run before PR merge.
