# New Brief Start Prompt

## Problem

After a user saves a project brief, the Start composer currently receives only
`product_goal`. That preserves the most important field, but it throws away the
context the user just typed into `project_type`, `target_users`,
`success_criteria`, `first_milestone`, `stack_preferences`, `constraints`, and
`notes` at the exact moment Trinity should turn that brief into actionable work.

For new projects, this weakens the first prompt after the brief modal. The user
has already provided enough structure for Trinity to plan initial work packages,
but the composer looks like a generic single-line request.

## Goals

- Build a concise Start prompt from the saved project brief when enough fields
  are present.
- Include the goal, type, users, success criteria, milestone, stack,
  constraints, and notes when provided.
- Use different lead-in text for new projects and existing projects.
- Only seed the composer when it is empty.
- Keep the previous single-line behavior when only `product_goal` exists.

## Non-Goals

- Do not auto-submit the prompt.
- Do not change the project intake schema.
- Do not change provider prompt injection or project-intake Markdown output.
- Do not overwrite user-written composer text.

## Design

1. Add a small prompt builder in the Textual app layer.
2. Reuse the builder from both initial Start prompt loading and project brief
   save handling.
3. Keep formatting deliberately plain text so it remains editable in the
   composer.
4. Preserve the existing target check before seeding the Start composer.

## Tests

- Initial Start prompt uses the full saved brief for the active workspace.
- Saving the Start project brief seeds a multiline prompt containing the
  relevant brief fields.
- Existing focused Textual tests continue to validate intake writes and summary
  refreshes.
