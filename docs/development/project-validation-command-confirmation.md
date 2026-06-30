# Project Validation Command Confirmation

Date: 2026-06-29
Branch: `feature/project-validation-confirmation`
Status: Superseded by the simplified Start/Nexus project flow.

Note: Start/Nexus no longer expose a dedicated validation modal. Validation
signals remain part of project intake and analysis prompts, but users should not
have to pick a separate setup tool before describing the work they want.

## Problem

The new/existing project onboarding flow can show a validation plan while still
letting users continue setup without an explicit runnable check.

This is risky in both first-run journeys:

- New project users may complete the minimum brief and move toward planning or
  execution without recording the command that proves the scaffold works.
- Existing project users may analyze a repository with docs/source anchors but no
  detected test or build command, then continue as if the project is ready.
- The Start/Nexus readiness labels currently treat generated validation hints as
  "planned", which can hide the fact that no user-confirmed check exists.

## Goal

Make validation confirmation a first-class setup step before Start planning or
Nexus execution when the saved project intake has no usable validation command.

## User Experience

### New Project

After the target folder exists and the minimum brief is complete:

1. `Continue Setup` checks the saved intake.
2. If no `validation_commands`, detected test command, or build command exists,
   Trinity keeps the missing validation signal in the project intake and prompt.
3. The user records at least one validation command, such as `uv run pytest`.
4. Start/Nexus labels refresh, and `Continue Setup` can proceed to plan/execute.

### Existing Project

After analysis and optional scope selection:

1. `Continue Setup` checks detected/recorded validation commands.
2. If no test/build/validation command exists, Trinity keeps the missing
   validation signal in the project intake and prompt.
3. The user records test/build/required validation commands.
4. The read-first prompt and validation plan use the saved commands.

## Implementation Plan

- Add project-intake helpers for "usable validation commands" and "validation
  missing" so CLI labels, Start/Nexus runtime, and Textual labels share the same
  rule.
- Extend `ProjectStartNextAction` with `validation`.
- Keep validation command edits inside project intake/analyze flows instead of a
  dedicated modal.
- Keep Start/Nexus free of validation setup modals; surface missing validation
  through project-intake summaries, prompts, and execution preflight.
- Refresh intake labels and seed the relevant prompt after saving.
- Update tests for new/existing project next actions, labels, and Textual modal
  behavior.

## Non-Goals

- Do not execute validation commands in this slice.
- Do not block direct `Plan first` or manual slash commands.
- Do not redesign the full project brief or anchor review forms.

## Success Criteria

- Missing validation is visible in project-intake summaries and preflight before
  execution.
- Saving validation commands updates `.trinity/project-intake.json`.
- The validation plan shows user-recorded commands before generated fallbacks.
- Existing tests and required smoke tests pass.
