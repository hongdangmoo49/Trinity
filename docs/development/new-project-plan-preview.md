# New Project Plan Preview

## Problem

New-project onboarding now records a project brief and seeds a strong Start/Nexus
prompt. However, the Workbench still hides most of the first-plan interpretation
inside the composer text. Users who are starting a new project should be able to
verify the first milestone, stack, and success direction before asking agents to
plan or scaffold.

## Scope

- Add a compact Workbench preview for saved `mode == "new"` project intake.
- Show the preview on both Start and Nexus below the existing project-intake
  summary.
- Derive the preview from saved brief fields only:
  `first_milestone`, `stack_preferences`, `success_criteria`, `target_users`,
  and `constraints`.
- Refresh the preview whenever Start/Nexus refresh project-intake summary labels.
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

Start and Nexus mount one extra `Static` widget below their project-intake
summary. Their existing `refresh_project_intake_summary()` methods update both
the summary and preview so no new app-level refresh path is needed.

## Tests

- The shared preview helper returns an English and Korean preview for new intake.
- Existing-project intake returns no preview.
- Start shows the preview after saving a new-project brief.
- Nexus shows the preview after saving a new-project brief.
