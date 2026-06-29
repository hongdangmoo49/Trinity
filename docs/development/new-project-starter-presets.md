# New Project Starter Presets

Date: 2026-06-29
Branch: `feature/new-project-starter-presets`

## Problem

The new-project brief asks for a free-form starter profile, stack preferences,
run commands, validation commands, and artifact targets. This is flexible, but
first-time users may not know what to type before Trinity has produced any
files.

The current flow makes new-project onboarding feel heavier than it needs to be:

- Users must invent starter wording from scratch.
- Run and validation commands can remain blank until a later confirmation step.
- The generation preview can be less useful when starter context is sparse.

## Goal

Add small starter preset buttons to the new-project brief modal so common project
shapes can be selected quickly and consistently.

## Presets

Initial presets should cover practical first-project shapes:

- Python CLI
- Textual TUI
- FastAPI Service
- Vite Web
- Empty

Selecting a preset should update:

- `starter_profile`
- `stack_preferences`
- `run_commands`
- `validation_commands`
- `artifact_targets`

## User Experience

1. User creates or analyzes an empty target as a new project.
2. The project brief modal shows starter preset buttons above the fields.
3. User selects a preset.
4. Related fields are filled immediately and the generation preview refreshes.
5. User can still edit any field manually before saving.

## Non-Goals

- Do not generate files in this slice.
- Do not make presets provider-specific.
- Do not remove free-form editing.

## Success Criteria

- Presets are visible only for new-project briefs.
- Clicking a preset fills the expected fields.
- Existing-project brief behavior is unchanged.
- Tests and required smoke pass.
