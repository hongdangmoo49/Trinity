# New Project Generation Conflict Preview

## Context

New-project intake already shows a generation preview based on starter profile,
project type, stack preferences, and validation hints. The preview tells users
which files/directories Trinity is likely to create, but it does not identify
whether those paths already exist in the selected target workspace.

That matters for both new and existing project starts:

- A user may select a non-empty folder by mistake.
- A newly created folder may already contain a README or source directory.
- A starter profile may imply files that collide with an existing scaffold.

## Goal

Add conflict hints to the generation preview when expected generated paths
already exist in the target workspace.

## Scope

- Reuse the existing `_new_project_generation_files` expected path list.
- Check expected file/directory paths under `ProjectIntake.target_workspace`.
- Append a compact `conflicts` section only when collisions exist.
- Keep existing generation preview output unchanged for empty workspaces.
- Cover English and Korean labels.

## Non-goals

- Do not block project creation.
- Do not modify filesystem contents.
- Do not add a modal or new workflow step.
- Do not change starter profile inference.

## Expected Behavior

- Empty new workspace: existing generation preview remains unchanged.
- Non-empty new workspace: preview includes `conflicts: ...`.
- Target mismatch: preview remains hidden as before.

## Test Plan

- Unit test empty new-project preview is unchanged.
- Unit test existing expected paths append conflicts.
- Unit test Korean conflict label.
- Run required smoke tests before version bump and PR.
