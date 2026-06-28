# Project Intake Workspace Profile

This document defines the first workspace-profile extension for Trinity project
intake. The goal is to make new and existing project starts provide enough
orientation for agents before they plan or edit files.

## Problem

The previous intake artifact recorded the selected target workspace, Git state,
package managers, and likely test commands. That was enough to prove that
Trinity was pointed at the right directory, but not enough to tell agents where
to begin reading, how to run the app locally, or which documentation files should
anchor the first response.

This is especially visible in two user journeys:

- Existing project: the user expects Trinity to inspect the selected project,
  respect existing structure, and avoid treating the control repo as the target.
- New project: the user expects Trinity to treat the selected folder as a fresh
  product workspace and start from bootstrap assumptions rather than stale repo
  context.

## Contract

Project intake now includes read-only workspace profile fields:

- `dev_commands`: likely local development commands.
- `build_commands`: likely build/package commands.
- `entrypoints`: likely CLI, app, or package entrypoints.
- `source_roots`: common source/test directories.
- `docs_found`: documentation files and folders worth reading first.

These fields must be safe to compute during Start/Nexus selection. They must not
execute package managers, tests, build tools, or user code. Older intake JSON
without these fields remains valid and loads with empty tuples.

## Prompt Guidance

Provider prompts include mode-specific project intake guidance when both
`project-intake.json` and `project-intake.md` are present. Existing projects are
framed as established workspaces that should be read before edits. New projects
are framed as fresh workspaces that should confirm product goal, stack, and first
milestone before scaffolding.

The guidance is derived from persisted intake JSON. Legacy states with only
`project-intake.md` keep the older prompt shape and include the Markdown context
without extra guidance.

## Detection Scope

The profile intentionally uses conservative filesystem and manifest checks:

- Python: `pyproject.toml`, `project.scripts`, `main.py`, `app.py`, `cli.py`,
  `manage.py`, and `build-system.build-backend`.
- Node: `package.json` scripts, `main`, and `bin` fields.
- Rust: `Cargo.toml`, `src/main.rs`.
- Go: `go.mod`, `main.go`, and `cmd`.
- Java: Maven and Gradle manifests.
- Docs: README variants, CONTRIBUTING, CHANGELOG, and `docs/`.

Broad semantic classification remains out of scope for this patch. Product
intent, target audience, stack preference, and milestone choices should be added
through a separate brief step for new projects.
