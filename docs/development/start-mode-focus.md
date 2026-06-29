# Start Mode Focus

Date: 2026-06-29
Branch: `feature/start-mode-focus`

## Problem

The Start screen supports both first-run journeys, but new-project and
existing-project actions are visible at the same level. Users can be unsure
whether `Continue Setup` will analyze an existing workspace or help create a new
one.

This matters most when:

- Trinity launches from the control repository.
- No target workspace has been selected yet.
- A user wants a new project and should not have to understand that "Select
  Workspace" comes before "Create New".

## Goal

Let the user choose a lightweight project-start focus before pressing
`Continue Setup`.

## User Experience

1. The Start screen shows a compact mode focus row.
2. User can choose `Existing` or `New`.
3. `Continue Setup` uses that focus:
   - Existing focus keeps the current workspace/analyze flow.
   - New focus opens the new-project creation flow directly when no matching new
     intake is ready.
4. Direct buttons such as `Analyze Existing` and `Create New` keep working.

## Implementation Plan

- Add an internal `project_mode_focus` state to `StartScreen`.
- Add two small focus buttons above the project-intake action row.
- Extend `project_setup_next_action` with a `preferred_mode` parameter.
- Refresh button variants when the focus changes.
- Add tests for preferred-mode routing and Start button state.

## Non-Goals

- Do not persist the focus setting.
- Do not remove existing direct action buttons.
- Do not redesign the full Start layout.
- Do not alter Nexus behavior in this slice.

## Success Criteria

- With New focus and no target, `Continue Setup` routes to create-new flow.
- With Existing focus and no target, `Continue Setup` still routes to workspace
  selection.
- The selected focus is visible through button variants.
- Existing Start actions and tests continue to pass.
