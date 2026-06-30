# Project Context Confirmation

Date: 2026-06-29
Branch: `feature/project-context-confirmation`

## Problem

Trinity now records useful project context for both first-run journeys, but the
user still has to infer which project context will be sent to agents:

- target workspace
- workspace context
- selected existing-project scope
- read-first confirmation state
- validation command state
- active provider/review policy
- execution risk signals

This is especially important when the user launches Trinity from the control
repository but selects a different target workspace, or when an existing-project
saved context is stale or sparse.

## Goal

Make the final pre-plan/pre-execute context visible and testable before agents
act on the project.

## User Experience

1. User prepares a new or existing project from Start or Nexus.
2. Before planning or execution, Trinity shows a compact project context
   summary in the existing confirmation surfaces.
3. The summary tells the user which target, workspace context, scope, read-first state,
   validation command, providers, and risks are active.
4. If a field is missing, the summary says so explicitly instead of staying
   silent.

## Implementation Plan

- Add a pure project-context summary builder that reads the selected target,
  saved project context, provider selection, and preflight risk state.
- Reuse the summary from the execution confirmation modal first.
- Keep modal behavior unchanged; this slice improves context visibility.
- Add tests for new-project and existing-project summaries so target/context/scope
  and validation state cannot silently drift.

## Non-Goals

- Do not introduce another blocking modal in this slice.
- Do not execute validation commands.
- Do not redesign the Start screen layout.
- Do not change provider execution or review routing.

## Success Criteria

- Execution confirmation shows a context summary derived from the selected
  workspace and matching project context.
- Existing-project summaries include selected scope and read-first state.
- New-project summaries include starter profile and validation state.
- Missing or mismatched project context states are explicit.
- Tests and required smoke pass.
