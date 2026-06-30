# Project Brief Cancel Draft Cache

## Problem

The project brief modal currently discards all typed values when the user
cancels or presses Escape. This is costly for both new-project and existing-
project starts because the brief can contain several fields and users may cancel
only to re-check the selected workspace or previous analysis.

## Scope

- Preserve canceled project brief edits for the current app session.
- Restore the canceled draft when reopening the brief for the same target
  workspace.
- Keep saved project context as the durable source of truth after Save.
- Do not persist canceled drafts to disk.
- Do not change saved project context JSON, readiness policy, preflight gates, or
  provider prompts.

## Design

Introduce an explicit modal result:

- `saved=True`: write saved project context exactly as today and clear any cached
  draft for the target.
- `saved=False`: cache the current modal draft in memory and do not write
  saved context.

`TrinityTextualApp` owns a small dictionary keyed by resolved target workspace
path. `_project_brief_draft_for_target` prefers:

1. cached unsaved draft for the same target;
2. saved context for the same target;
3. an empty draft.

This keeps cancel recovery local to the current Workbench session and avoids
surprising persistence of abandoned content.

## Tests

- Canceling a brief caches typed values without writing them as saved context.
- Reopening the same target restores the cached draft.
- Saving clears the cached draft and writes durable context.
- Different target workspaces do not receive another target's cached draft.
