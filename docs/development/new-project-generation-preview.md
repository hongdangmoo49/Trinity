# New Project Generation Preview

## Problem

New-project intake captures product intent and starter profile, and local
project diagnostics can show an initial plan preview. However, before execution
the user still needs a way to inspect what kind of files Trinity expects agents
to create or how the first generated state should be validated without adding
more Start/Nexus chrome.

For new projects, this creates uncertainty at the exact point where users are
about to allow writes into an empty or newly created workspace.

## Scope

- Add a derived generation preview for saved `mode == "new"` project intake.
- Show the preview through `/project` diagnostics and
  `trinity project status` text/JSON.
- Derive preview text from saved intake only: `starter_profile`, `project_type`,
  `stack_preferences`, `constraints`, and detected test commands.
- Keep the preview advisory and non-blocking.

## Non-Goals

- Do not generate files from this preview.
- Do not execute package managers or test commands.
- Do not add a template catalog or template selection wizard.
- Do not show the preview for existing-project intake.
- Do not change execute preflight gating.

## Design

Add a shared `project_generation_preview_label()` helper next to the existing
project-intake label helpers. It returns an empty string unless the saved intake
matches the selected new-project target.

The helper should render a compact localized line:

- English: `Generation preview: create ... | validate ... | guardrails ...`
- Korean: `생성 미리보기: 생성 ... | 검증 ... | 가드레일 ...`

File expectations are conservative and based on intent:

- Python/Textual/FastAPI/CLI: `README.md`, `pyproject.toml`, `src/`, `tests/`
- Node/React/Vite/web: `README.md`, `package.json`, `src/`, `tests/`
- Docs-first: `README.md`, `docs/`
- Fallback: `README.md`, `src/`, `tests/`

Validation should prefer detected `test_commands` when available. If no command
is detected yet, infer a first likely command from stack/profile text:

- Python/Textual/FastAPI/CLI: `uv run pytest`
- pnpm: `pnpm test`
- npm/Node/React/Vite/web: `npm test`
- Fallback: `define first smoke check`

The preview is intentionally short. It helps the user confirm the expected first
write shape before planning/execution without pretending that Trinity has already
generated a concrete file list.

## Tests

- Shared helper returns English and Korean generation previews for new intake.
- Existing-project intake returns no generation preview.
- CLI `project status` text and JSON include the preview for new intake.
- `/project` diagnostics and `trinity project status` refresh the preview after
  saving a new-project brief.
