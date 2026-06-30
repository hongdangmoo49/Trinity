# Existing Scope Picker

Status: Superseded by the simplified Workbench flow. Start/Nexus no longer
route `Continue Setup` through scope or anchor modals; selected scope remains
part of project intake and provider prompt context.

## Background

Existing-project analysis can detect subproject scope candidates such as
`apps/web` or `packages/core`. Trinity already stores `selected_scope`, and the
full analysis anchors modal lets users type it manually.

However, when an existing project has candidates but no selected scope, the
current Continue Setup path routes through the broader analysis flow. This feels
like the user is being asked to re-analyze the project even when the only
missing decision is the intended scope.

## Goal

- Treat missing existing-project scope as its own setup action.
- Add a focused scope picker modal for saved `scope_candidates`.
- Let Start and Nexus Continue Setup open this picker before planning/execution.
- Persist the selected scope to `.trinity/project-intake.json` and refresh the
  existing labels/prompts.

## Runtime Contract

Extend `ProjectStartNextAction` with `scope`.

Rules:

- existing intake with `scope_candidates` and blank `selected_scope` -> `scope`
- stale/changed intake still -> `analyze`
- no intake or target mismatch still -> `analyze`
- new-project brief flow remains unchanged

## UX

The modal shows:

- target workspace
- detected scope candidates
- selected scope input
- one quick-select button per candidate
- Cancel / Save Scope actions

The Analyze Existing button continues to open the full analysis anchors modal.
Only Continue Setup uses the focused picker when scope is the next missing
decision.

## Non-goals

- Do not change scope detection.
- Do not remove the selected-scope field from the anchors or brief modals.
- Do not alter execution gating.

## Validation

- Unit test `project_setup_next_action(...)=scope` for existing-project
  candidates.
- App tests for Start and Nexus Continue Setup opening the scope picker.
- Verify saved scope refreshes project-intake labels.
- `uv run python scripts/run_required_smoke_tests.py -q`
