# Existing Read-First Confirmation

Date: 2026-06-29
Branch: `feature/existing-read-first-confirmation`
Status: Superseded by the simplified Workbench flow. Start/Nexus no longer use
`Continue Setup` or `ProjectAnchorsModal`; read-first context remains a
project-intake signal rather than a Workbench modal step.

## Problem

Existing-project onboarding already detects docs, source roots, scope candidates,
and test/build anchors. The Start/Nexus screens also show a read-first checklist.
However, a saved intake does not record whether the user actually confirmed the
read-first set before planning or execution.

This leaves a gap for users who start from CLI-managed intake, stale state, or a
previous session:

- Trinity can show read-first hints but still continue setup without an explicit
  user confirmation.
- Existing-project work can feel less deliberate than new-project generation,
  which already has confirmation gates.
- The same `ProjectAnchorsModal` review is useful, but there is no persisted
  "confirmed" signal.

## Goal

Add a lightweight existing-project read-first confirmation step before validation
and ready state.

## User Experience

1. User selects or analyzes an existing project.
2. Trinity detects docs/source/scope/test/build anchors.
3. If the saved intake has not confirmed read-first anchors, `Continue Setup`
   opens the analysis anchor review modal.
4. Saving the modal marks read-first as confirmed and refreshes labels/prompts.
5. The next `Continue Setup` step can move to validation or ready state.

## Implementation Plan

- Add `read_first_confirmed` to `ProjectIntake` with backward-compatible loading.
- Mark the flag when `ProjectAnchorsModal` is saved.
- Add a pure helper for existing-project read-first confirmation requirements.
- Extend `ProjectStartNextAction` with `read_first`.
- Route Start/Nexus `Continue Setup` to the existing `ProjectAnchorsModal` when
  read-first confirmation is needed.
- Surface the state in labels and tests without forcing direct Plan/Execute
  commands to stop.

## Non-Goals

- Do not execute read-first file reads in this slice.
- Do not add another modal when the existing anchor review modal already covers
  the needed editable fields.
- Do not block new-project flow.

## Success Criteria

- Existing-project `Continue Setup` asks for read-first confirmation before
  validation/ready state when anchors exist and confirmation is missing.
- Saving the review persists `read_first_confirmed: true`.
- Existing project prompts and labels refresh after confirmation.
- Tests and required smoke pass.
