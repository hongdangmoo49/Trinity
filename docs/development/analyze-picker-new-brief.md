# Analyze Picker New Brief Handoff

## Problem

`Analyze Existing` can open the workspace picker when Trinity was launched from
the control repo or there is no safe target workspace. If the user selects an
empty directory in that picker, Workspace Preflight correctly classifies it as a
new-project candidate. Current handling writes a `new` project intake, but does
not open the project brief modal. The result is an incomplete new-project
intake with no immediate recovery step.

## Goals

- When Start `Analyze Existing` picker selection resolves to a new-project
  candidate, open the project brief modal after syncing intake.
- When Nexus `Analyze Existing` picker selection resolves to a new-project
  candidate, open the same project brief modal after target synchronization.
- Keep existing-project picker selections unchanged: write existing intake and
  seed the analysis prompt.
- Keep `Select Workspace`, `Create New`, project brief edit, and execute
  preflight flows unchanged.

## Non-Goals

- Do not rename the `Analyze Existing` action.
- Do not auto-submit prompts.
- Do not change Workspace Preflight classification rules.

## Design

1. Reuse the existing `created or new_project_candidate -> new` intake mode
   rule.
2. In Start analysis picker callback, if the preflight mode is `existing`, seed
   the existing-analysis prompt; otherwise open the new-project brief modal.
3. In Nexus analysis picker continuation, if the preflight mode is `existing`,
   seed the Nexus analysis prompt; otherwise open the new-project brief modal.
4. Keep cancellation behavior unchanged: cancelling the modal leaves the
   incomplete new-project intake visible through existing labels and execute
   safety gates.

## Tests

- Start `Analyze Existing` picker selecting an empty target opens the project
  brief modal and writes `new` intake.
- Nexus `Analyze Existing` picker selecting an empty target opens the project
  brief modal and writes `new` intake.
