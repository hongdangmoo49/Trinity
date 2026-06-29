# New Project Starter Profile

## Problem

New-project intake records the product goal, users, success criteria, stack, and
first milestone. That helps agents understand why the project exists, but it does
not clearly state what shape the initial project should take.

For a new project, users often know whether they want a CLI tool, Textual TUI,
FastAPI service, React app, Python package, or documentation-first repository.
If Trinity does not persist that starter shape, agents may spend the first round
asking broad template questions or propose scaffolding that does not match the
user's intent.

## Scope

- Add a backward-compatible `starter_profile` field to project intake.
- Let CLI users record it with `trinity project new/analyze --starter-profile`
  or `--starter`.
- Preserve the starter profile during `trinity project status --refresh`.
- Show it in project-intake JSON/Markdown, CLI status, Start/Nexus summaries,
  and the new-project plan preview.
- Add a Starter profile input to the Workbench Project Brief modal for new
  project flows.
- Include the starter profile in project-brief prompt seeding and provider
  guidance.

## Non-Goals

- Do not generate template files from this field yet.
- Do not execute package managers or install dependencies.
- Do not add a framework/template catalog.
- Do not make the starter profile mandatory for existing projects.

## Design

`ProjectIntake.starter_profile` is a user-provided text field that describes the
intended initial shape of a new project. Examples:

- `Textual TUI`
- `Python CLI package`
- `FastAPI service`
- `React/Vite web app`
- `docs-first repository`

The field is advisory and should influence planning, prompt guidance, and preview
text. It is separate from `project_type`:

- `project_type`: product/category from the user's point of view.
- `starter_profile`: implementation/repository shape for the first scaffold.

Older intake JSON without the field loads with an empty string.

## Tests

- Loading older intake without `starter_profile` remains valid.
- CLI `project new/analyze --starter-profile` persists and displays it.
- `project status --refresh` preserves the starter profile.
- Start/Nexus summaries and new-project plan preview include it.
- Project Brief modal saves it for new project flows.
- Prompt guidance includes it for new project planning.
