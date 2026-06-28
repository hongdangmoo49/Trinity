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

Project intake also includes optional user-provided project brief fields:

- `product_goal`: the outcome the user wants the target project to achieve.
- `project_type`: the type or category of product being started or improved.
- `target_users`: the primary users or audience the product should serve.
- `success_criteria`: how the user will recognize that the first outcome works.
- `stack_preferences`: preferred technologies, frameworks, or runtime choices.
- `first_milestone`: the first concrete milestone agents should optimize for.
- `constraints`: boundaries such as "no network dependency" or "keep tests
  green".

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

CLI users can record the brief with `trinity project new` or
`trinity project analyze`:

- `--goal TEXT`
- `--project-type TEXT`
- `--target-users TEXT`
- `--success-criteria TEXT`
- `--stack TEXT` repeated or comma-separated
- `--milestone TEXT`
- `--constraint TEXT` repeated or comma-separated

`trinity project status --refresh` refreshes filesystem-derived analysis while
preserving the saved project brief.

Workbench project-intake sync follows the same preservation rule. When the
current saved intake points at the same target workspace, Start/Nexus workspace
sync preserves the saved brief and notes while refreshing filesystem-derived
analysis. When the target changes, the saved brief is not carried to the new
workspace.

When Trinity opens the Workbench and the saved intake target matches the active
workspace candidate, Start seeds the composer with `product_goal`. This avoids
asking CLI users to retype the same new/existing project goal before planning.

Start and Nexus also expose a Workbench "Edit Brief" action. It writes the same
project brief and product discovery fields as the CLI flags, refreshes the
project-intake summary, and keeps the active target workspace unchanged. Saving
a product goal from Start also seeds the Start composer when the composer is
still empty.

For new projects, Trinity treats `product_goal`, `project_type`,
`target_users`, `success_criteria`, and `first_milestone` as the minimum brief
needed before high-quality scaffolding. CLI summaries, `project status`, and
Start/Nexus project-intake labels show whether that new-project brief is
complete or which fields are still missing. Existing projects do not show this
readiness warning because read-only workspace analysis is the stronger first
signal for that journey.

For existing projects, Start/Nexus project-intake labels include the saved Git
state from the latest intake analysis. Non-Git workspaces show `git: none`, clean
repositories show the branch and clean state, and dirty repositories show saved
dirty and untracked counts. This keeps the selected project safety signal visible
before planning or execution. The same labels also surface detected source roots,
so existing-project users can confirm that Trinity found the expected source and
test directories before asking agents to plan against the project.

Provider prompt guidance uses the same readiness contract. When a new-project
brief is incomplete, providers are told to confirm the missing fields before
scaffolding and to avoid treating framework or UX choices as final. When the
brief is complete, providers are told to use the recorded goal, type, users,
success criteria, stack, milestone, and constraints as planning constraints.
Existing-project prompts treat any recorded brief fields as user intent that
must still be checked against the existing docs and source.

## Detection Scope

The profile intentionally uses conservative filesystem and manifest checks:

- Python: `pyproject.toml`, `project.scripts`, `main.py`, `app.py`, `cli.py`,
  `manage.py`, and `build-system.build-backend`.
- Node: `package.json` scripts, `main`, and `bin` fields.
- Rust: `Cargo.toml`, `src/main.rs`.
- Go: `go.mod`, `main.go`, and `cmd`.
- Java: Maven and Gradle manifests.
- Docs: README variants, CONTRIBUTING, CHANGELOG, and `docs/`.

Broad semantic classification remains out of scope for this patch. Richer
template recommendation and interactive branching questions should be added
later after the saved product discovery fields prove useful in real workflows.
