# Saved Project Context Target Guard

## Context

Trinity persists saved project context under the control repository state
directory. That context is useful prompt context for both new-project and
existing-project workflows, but it is only valid for the target workspace it was
recorded from.

If a user switches the Nexus target workspace and starts a new workflow before
refreshing saved context, providers can receive stale project facts from the
previous target. This creates the wrong user experience: the UI says one
workspace is selected, while provider prompts may still contain analysis for
another project.

## Goal

Make provider prompt context target-aware for saved project context.

## Scope

- Let `project_intake_prompt_block` accept the current target workspace.
- If persisted context belongs to a different target, return a compact stale
  context guard instead of the old saved context markdown.
- Pass the current target workspace from both central-agent prompts and
  deliberation round prompts.
- Keep the existing behavior unchanged when no target workspace is provided.

## Non-goals

- Do not re-run project analysis automatically.
- Do not delete stale context artifacts.
- Do not block workflow start.
- Do not add saved project context labels back into Start/Nexus; `/project`
  diagnostics own that detail.

## Expected Behavior

- Matching target: include guidance plus `project-intake.md` as before.
- Missing target: include existing prompt block behavior as before.
- Mismatched target: tell providers the saved context is stale and must not be
  used as project facts.

## Test Plan

- Unit test matching target includes the normal saved context block.
- Unit test mismatched target returns stale-context guidance and omits markdown
  facts from the previous project.
- Unit test central and deliberation prompt builders pass target workspace into
  `project_intake_prompt_block`.
