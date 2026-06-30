# New Brief Start Prompt

## Problem

This note predates the prompt-led Workbench simplification. Earlier designs
seeded the Start composer from saved project brief fields, but that made the
first prompt look authored by Trinity instead of the user.

For new projects, the saved brief still matters: it is preserved in project
intake, shown through `/project` diagnostics and CLI status, and injected into
provider prompt guidance. The composer itself stays blank until the user writes
the actual analysis or work request.

## Goals

- Keep the Start composer user-authored.
- Preserve saved brief fields in project intake, diagnostics, CLI status, and
  provider prompt guidance.
- Avoid injecting `product_goal` or a generated multiline prompt into the
  composer.

## Non-Goals

- Do not auto-submit the prompt.
- Do not change the project intake schema.
- Do not change provider prompt injection or project-intake Markdown output.
- Do not overwrite user-written composer text.

## Design

1. Leave the Textual Start composer empty unless explicit initial text is passed.
2. Keep saved brief fields in the existing project-intake artifacts.
3. Let `/project`, `trinity project status`, and provider prompt guidance render
   brief context when needed.
4. Preserve the target check before using saved brief context in diagnostics or
   provider prompts.

## Tests

- Initial Start prompt stays blank even when saved brief context exists.
- Submitting a user-written prompt starts the workflow with exactly that text.
- Existing focused Textual tests continue to validate intake writes and
  diagnostics.
