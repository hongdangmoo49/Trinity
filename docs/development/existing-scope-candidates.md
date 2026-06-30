# Existing Project Scope Candidates

## Problem

Existing-project analysis can now show read anchors and let users correct them.
For monorepos and multi-package projects, the selected target workspace may be
the repository root while the real work belongs under `apps/*`, `packages/*`,
`services/*`, or similar subprojects.

Without surfacing these scope candidates, users and agents may plan against the
whole repository when the next safe step should first choose a narrower package
or app.

## Scope

- Add a backward-compatible `scope_candidates` field to the saved project
  context.
- Detect likely scope candidates read-only from common workspace directories and
  package workspace globs.
- Include scope candidates in saved project context JSON and Markdown.
- Include scope candidates in existing-project drift detection.
- Show scope candidates in `/project` diagnostics and CLI status summaries.
- Include scope candidates in existing-project analysis seed prompts when
  present.

## Non-Goals

- Do not auto-select a scope.
- Do not create or move files.
- Do not execute package managers, tests, or workspace commands.
- Do not block planning or execution.

## Design

`detect_scope_candidates(path)` should inspect only the filesystem and
manifest metadata. It returns relative paths such as:

- `apps/web`
- `packages/core`
- `services/api`

Detection sources:

1. Conventional parent directories: `apps`, `packages`, `services`, `libs`,
   `crates`, `modules`.
2. Child directories with common manifest files:
   `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `pom.xml`,
   `build.gradle`, `build.gradle.kts`.
3. Node `package.json` workspace globs such as `apps/*` or `packages/*`.

The field is advisory. It helps users see that the repository may need a
smaller scope before planning, but it does not change target workspace or
execution behavior.

## Tests

- `detect_scope_candidates` detects conventional app/package/service folders.
- `build_project_intake` persists scope candidates to JSON and Markdown.
- Loading older intake without the field remains valid.
- Existing-project drift detects changed scope candidates.
- `/project` diagnostics, CLI status, and existing-analysis prompt include
  scope candidates.
