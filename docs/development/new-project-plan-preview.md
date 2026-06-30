# New Project Plan Preview

## Problem

New-project onboarding records a project brief and seeds a strong prompt.
However, users who are starting a new project still need a compact way to verify
the first milestone, stack, and success direction before asking agents to plan
or scaffold.

## Scope

- Add a compact preview for saved `mode == "new"` project intake.
- Show the preview through `/project` diagnostics and
  `trinity project status`, not as always-visible Start/Nexus chrome.
- Derive the preview from saved brief fields only:
  `first_milestone`, `stack_preferences`, `success_criteria`, `target_users`,
  and `constraints`.
- Refresh the preview whenever project diagnostics or CLI status read the saved
  project intake.
- Keep existing prompt seeding behavior unchanged.
- Keep existing-project UI unchanged by rendering no preview for existing intake.

## Non-Goals

- Do not generate files or templates.
- Do not execute package managers or validation commands.
- Do not add a blocking confirmation step before planning.
- Do not change the project-intake schema.

## Design

Add a shared `project_plan_preview_label` helper next to the existing workspace
label helpers. It loads the saved project intake and returns an empty string
unless the saved intake is for the selected new-project target.

For complete or partially complete new-project brief data, render a concise
localized label:

- English: `Initial plan preview: milestone ... | stack ... | success ...`
- Korean: `초기 계획 미리보기: 마일스톤 ... | 스택 ... | 성공 ...`

Project diagnostics reuse the helper when building `/project` output, and CLI
status formats the same saved intake state. No Start/Nexus widget is required.

## Tests

- The shared preview helper returns an English and Korean preview for new intake.
- Existing-project intake returns no preview.
- `/project` shows the preview after saving a new-project brief.
- `trinity project status` shows the preview after saving a new-project brief.
