# New Brief Missing Field Prompt

## Problem

New-project onboarding now captures a project brief and seeds Start/Nexus
prompts after the brief is saved. When the user saves only a product goal, the
seeded prompt can collapse to the goal text. That is concise, but it loses the
readiness signal already tracked by project intake: a new project should confirm
type, users, success criteria, and first milestone before agents scaffold files.

This matters for first-run users. They may intentionally enter a rough idea and
expect Trinity to ask the missing product questions instead of assuming choices.

## Scope

- Add missing-field guidance to the seeded brief prompt for `mode == "new"`.
- Use the same minimum brief fields already used by readiness checks:
  `project_type`, `target_users`, `success_criteria`, and `first_milestone`
  when they are empty.
- Keep existing-project prompts unchanged.
- Keep complete new-project prompts unchanged except for no missing-field block.
- Preserve the existing behavior where an empty product goal produces no seeded
  prompt.

## Design

The prompt builder remains the single source of seeded Start/Nexus prompt text:
`_project_brief_start_prompt`.

For new projects:

1. Build the existing populated brief lines.
2. Compute missing minimum fields after trimming whitespace.
3. If any minimum fields are missing, append a short "Confirm before
   scaffolding" block in the active UI language.
4. Do not add the block for existing projects.

This is prompt-only guidance. It does not change persisted intake, readiness
policy, preflight gates, or modal validation.

## Tests

- New-project prompt with only a goal includes the missing-field block.
- Korean new-project prompt includes localized missing-field labels.
- Existing-project prompt with sparse brief does not include the block.
- Complete new-project prompt does not include the block.
