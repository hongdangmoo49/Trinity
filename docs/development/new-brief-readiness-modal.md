# New Brief Readiness Modal

## Problem

New-project intake already tracks the minimum brief fields needed for useful
first scaffolding: goal, project type, target users, success criteria, and first
milestone. Start/Nexus labels can warn that the brief is incomplete, but the
brief modal itself does not show that readiness state while the user edits the
fields.

This makes the new-project path feel less guided than it should. Users can open
the correct form but still need to infer which fields matter before execution.

## Goal

Show a compact, live readiness line inside the new-project brief modal so users
can see whether the minimum brief is complete before saving.

## Scope

- Add a readiness status line to `ProjectBriefModal` when `mode == "new"`.
- Mark the five minimum fields as missing or complete:
  - product goal
  - project type
  - target users
  - success criteria
  - first milestone
- Update the readiness line as inputs change.
- Keep existing save/cancel behavior and preflight gates unchanged.
- Do not show this readiness line for existing-project brief editing.

## Validation

- Modal tests cover English and Korean readiness copy.
- A focused dynamic update test verifies that filling required fields changes
  the readiness line from missing to complete.
- Required smoke tests run before PR merge.
