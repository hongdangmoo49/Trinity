# Local Lookup Command Title Korean Localization

## Context

Several local lookup slash commands already render Korean bodies, tables, and hints, but their modal/central titles are still hard-coded in English.

Affected commands:

- `/workflow`
- `/questions`
- `/decisions`
- `/packages`
- `/subtasks`
- `/history`

## Scope

- Add presenter title helpers for the local lookup command group.
- Route Textual app command result titles through those helpers.
- Keep English titles unchanged.
- Add Korean title assertions to existing Textual command tests.
- Bump the patch version for the PR.

## Validation

- Run focused local lookup command tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run the full pytest suite before merge.
