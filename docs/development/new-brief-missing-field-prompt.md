# New Brief Missing Field Prompt

## Problem

New-project onboarding captures a project brief, but the prompt-led Workbench no
longer seeds Start/Nexus composers from saved brief fields. When the user saves
only a product goal, the saved intake still needs to carry the readiness signal:
a new project should confirm type, users, success criteria, and first milestone
before agents scaffold files.

This matters for first-run users. They may intentionally enter a rough idea and
expect Trinity to ask the missing product questions instead of assuming choices.

## Scope

- Add missing-field guidance to saved intake diagnostics and provider prompt
  guidance for `mode == "new"`.
- Use the same minimum brief fields already used by readiness checks:
  `project_type`, `target_users`, `success_criteria`, and `first_milestone`
  when they are empty.
- Keep existing-project prompts unchanged.
- Keep complete new-project guidance unchanged except for no missing-field
  block.
- Preserve the current behavior where the Start composer stays user-authored.

## Design

Project-intake guidance remains the single source of brief readiness context for
providers and diagnostics.

For new projects:

1. Build the existing populated brief lines in project-intake guidance.
2. Compute missing minimum fields after trimming whitespace.
3. If any minimum fields are missing, append a short "Confirm before
   scaffolding" block in the active UI language.
4. Do not add the block for existing projects.

This is prompt/diagnostic guidance. It does not change persisted intake,
readiness policy, preflight gates, or modal validation.

## Tests

- New-project guidance with only a goal includes the missing-field block.
- Korean new-project guidance includes localized missing-field labels.
- Existing-project guidance with sparse brief does not include the block.
- Complete new-project guidance does not include the block.
