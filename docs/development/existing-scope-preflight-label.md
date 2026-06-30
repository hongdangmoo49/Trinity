# Existing Scope Preflight Label

## Problem

Saved existing-project context can now persist a `selected_scope`, and the
analysis prompt includes that scope. However, the Execute Preflight modal still
shows the target workspace only at repository level. For monorepo users, this
makes the last confirmation before execution less explicit than the earlier
analysis step.

## Goal

Show the saved selected scope in Execute Preflight when the current target
workspace matches the saved existing-project context.

## Scope

- Add an optional scope label to `WorkspacePreflight`.
- Populate it from `project-intake.json` only when:
  - saved project context exists and is readable,
  - saved project context mode is `existing`,
  - saved project context target matches the preflight target,
  - `selected_scope` is non-empty.
- Render the scope in English and Korean preflight output.
- Keep execution permissions, safety warnings, and prompt contracts unchanged.

## Validation

- Workspace picker unit tests cover matching selected scope, target mismatch,
  and saved new-project context not rendering a scope label.
- Required smoke tests run before PR merge.
