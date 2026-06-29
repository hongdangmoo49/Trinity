# Project Intake Target Guard

## Context

Trinity persists project intake under the control repository state directory.
That intake is useful prompt context for both new-project and existing-project
workflows, but it is only valid for the target workspace it was recorded from.

If a user switches the Nexus target workspace and starts a new workflow before
refreshing intake, providers can receive stale project facts from the previous
target. This creates the wrong user experience: the UI says one workspace is
selected, while provider prompts may still contain analysis for another project.

## Goal

Make project intake prompt context target-aware.

## Scope

- Let `project_intake_prompt_block` accept the current target workspace.
- If persisted intake belongs to a different target, return a compact stale
  intake guard instead of the old intake markdown.
- Pass the current target workspace from both central-agent prompts and
  deliberation round prompts.
- Keep the existing behavior unchanged when no target workspace is provided.

## Non-goals

- Do not re-run project analysis automatically.
- Do not delete stale intake artifacts.
- Do not block workflow start.
- Do not change the visible project intake labels in Start/Nexus.

## Expected Behavior

- Matching target: include guidance plus `project-intake.md` as before.
- Missing target: include existing prompt block behavior as before.
- Mismatched target: tell providers the saved intake is stale and must not be
  used as project facts.

## Test Plan

- Unit test matching target includes the normal intake block.
- Unit test mismatched target returns stale-intake guidance and omits markdown
  facts from the previous project.
- Unit test central and deliberation prompt builders pass target workspace into
  `project_intake_prompt_block`.
