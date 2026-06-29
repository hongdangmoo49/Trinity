# New Project Brief Validation Context

## Background

Trinity already asks for the core new-project brief: goal, type, users, success
criteria, stack, and first milestone. That is enough for high-level planning, but a
user starting a brand-new project still has to repeat practical delivery details:

- how the project should be run locally,
- how the first milestone should be validated,
- where initial implementation artifacts should live.

Without these details, agents may propose generic scaffolding or validation steps that
do not match the user's intended workflow.

## Goal

- Add optional new-project brief fields for practical delivery context.
- Persist the fields in project intake JSON and Markdown.
- Include the fields in provider prompt context through the existing project intake
  block.
- Keep existing-project brief UX unchanged except for preserving the values when they
  already exist.

## Fields

- `run_commands`: local commands the user expects to run during development.
- `validation_commands`: commands or checks that should prove the first milestone.
- `artifact_targets`: relative files or directories where initial output should be
  created.

These are optional. The minimum brief remains goal, type, users, success criteria, and
first milestone.

## User Experience

For a new project, the Project Brief modal should show:

```text
Run commands          npm run dev, uv run trinity
Validation commands   npm test, uv run pytest
Artifact targets      apps/web, src/trinity
```

The saved intake should then appear in the Markdown brief and prompt context so work
packages can include concrete validation and output locations from the start.

## Non-goals

- Do not require these fields before planning.
- Do not infer commands from an empty new-project folder.
- Do not change execution semantics; these values guide planning only.

## Validation

- Unit tests for serialization and Markdown output.
- Modal tests for preserving and saving the new fields.
- Start/Nexus prompt seeding tests continue to pass.
- Required smoke tests before merge.
