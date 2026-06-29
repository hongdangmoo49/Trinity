# Existing Project Selected Scope

## Problem

Existing-project intake can now detect likely monorepo scope candidates such as
`apps/web`, `packages/core`, or `services/api`. That helps users notice that the
repository may contain multiple work areas, but Trinity still has no persisted
way to record which scope the user actually wants agents to discuss or edit.

Without an explicit selected scope, Start/Nexus summaries and provider prompts
can still drift back to repository-wide planning even after the user has a
specific app or package in mind.

## Scope

- Add a backward-compatible `selected_scope` field to project intake.
- Let CLI users record it with `trinity project analyze --scope SCOPE`.
- Preserve the selected scope during `trinity project status --refresh`.
- Show the selected scope in project-intake Markdown, CLI status JSON/text, and
  Start/Nexus summaries.
- Show the selected scope in the existing-project Edit Brief modal.
- Include the selected scope in provider prompt guidance and existing-analysis
  seed prompts.

## Non-Goals

- Do not auto-select a scope from `scope_candidates`.
- Do not change the target workspace path.
- Do not execute package managers, tests, or workspace commands.
- Do not block planning or execution when the selected scope is missing.
- Do not rewrite work package routing around scope-aware execution yet.

## Design

`ProjectIntake.selected_scope` is a user-provided relative path string. It is
stored separately from `scope_candidates`:

- `scope_candidates`: read-only detected hints.
- `selected_scope`: user-confirmed work area for the next planning/execution
  conversation.

The value is advisory but prominent. Existing-project prompt guidance should tell
providers to treat the selected scope as the primary work area and to avoid broad
repository edits unless the user asks for them.

The field remains valid for older intake JSON by loading a missing value as an
empty string. New-project intake can technically carry the field for schema
stability, but UI entry and prompt guidance focus it on existing-project flows.

## Tests

- Loading older intake without `selected_scope` remains valid.
- `trinity project analyze --scope apps/web` persists and displays the scope.
- `trinity project status --refresh` preserves the selected scope.
- Start/Nexus project-intake summaries show the selected scope.
- Existing-project prompt guidance and analysis seed prompts include it.
- The Edit Brief modal can load, edit, and save the selected scope.
