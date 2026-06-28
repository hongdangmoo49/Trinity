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

`trinity init --mode new --project-name NAME` can also create the initial
target workspace during setup and write the same new-project intake artifacts.
If `--project-name` is provided without `--mode`, init treats the flow as new
project onboarding. `--mode new` without `--project-name` keeps the older
deferred behavior and prints the `trinity project new NAME --parent PATH` next
step.

When a new-project brief is incomplete, `trinity project new`,
`trinity project analyze --mode new`, and `trinity project status` include a
completion command containing only the missing brief fields. This lets users
fill the minimum product goal, type, users, success, and milestone context
before running `trinity`.

`trinity project status --refresh` refreshes filesystem-derived analysis while
preserving the saved project brief.

`trinity project status` also prints the same compact project-intake summary
used by Start/Nexus before the detailed saved/current analysis sections. This
lets CLI users verify the Workbench-facing target, brief, test, and safety
signals without opening the Textual UI. JSON status includes the same compact
summary under `project_intake.summary` so scripts can reuse the same readiness
signal without scraping panel text.
JSON status also exposes `project_intake.readiness` and
`project_intake.action_variants`. These fields provide target existence,
sparse/stale analysis, missing new-project brief fields, the recommended next
action, and the Workbench-equivalent Analyze Workspace/Create Project/Edit Brief
button variants without requiring callers to parse the compact summary string.

Workbench project-intake sync follows the same preservation rule. When the
current saved intake points at the same target workspace, Start/Nexus workspace
sync preserves the saved brief and notes while refreshing filesystem-derived
analysis. When the target changes, the saved brief is not carried to the new
workspace.

When no project intake has been recorded yet, Start/Nexus project-intake labels
use the currently selected workspace candidate to show a concrete
`trinity project analyze <path>` next step. If no workspace is selected, the
generic existing/new project commands remain visible.

When Trinity opens the Workbench and the saved intake target matches the active
workspace candidate, Start seeds the composer with `product_goal`. This avoids
asking CLI users to retype the same new/existing project goal before planning.

When saved project intake exists but points at a different workspace than the
current Start/Nexus target, the project-intake label shows a target mismatch
warning. This prevents users from planning against one workspace while the saved
analysis and brief still describe another.

When the saved intake target no longer exists, Start/Nexus and
`trinity project status` mark the compact summary as target missing. This
prevents users from trusting stale intake after moving, deleting, or renaming a
project folder. CLI status next steps prefer target recovery in this state:
existing projects are sent back to `trinity project analyze [PATH]`, while new
projects are given a `trinity project new <name> --parent <path>` recreation
command.

Start and Nexus also expose a Workbench "Edit Brief" action. It writes the same
project brief and product discovery fields as the CLI flags, refreshes the
project-intake summary, and keeps the active target workspace unchanged. Saving
a product goal from Start also seeds the Start composer when the composer is
still empty.

Workbench action buttons use the same intake readiness policy as the compact
summary. The analyze action is highlighted when selected-workspace analysis is
missing, mismatched, stale, sparse, unreadable, or points at a missing existing
target. The create action is highlighted when a saved new-project target no
longer exists. The brief action remains focused on incomplete new-project brief
fields.
Start and Nexus expose those actions with journey-oriented labels:
`Analyze Existing`, `Create New`, and `Edit Brief` in English, and
`기존 프로젝트 분석`, `새 프로젝트 생성`, and `브리프 편집` in Korean. The
underlying action IDs remain stable so existing readiness and variant logic can
continue to use `analyze_workspace`, `create_project`, and `edit_brief`.

For new projects, Trinity treats `product_goal`, `project_type`,
`target_users`, `success_criteria`, and `first_milestone` as the minimum brief
needed before high-quality scaffolding. CLI summaries, `project status`, and
Start/Nexus project-intake labels show whether that new-project brief is
complete or which fields are still missing. Existing projects do not show this
readiness warning because read-only workspace analysis is the stronger first
signal for that journey.

When a saved new-project brief is incomplete for the selected workspace,
Start/Nexus highlight the Workbench "Edit Brief" action. Once the minimum brief
is complete, the action returns to the default visual priority.

When the Workbench preflight sees an existing empty non-Git directory, it treats
that directory as a new-project candidate instead of an existing project. This
lets users create a folder outside Trinity first, select it, and still get
new-project intake guidance and brief readiness instead of sparse existing
project analysis warnings. Non-empty directories continue to use existing
project intake unless they were created by the Workbench new-folder flow.

Start/Nexus project-intake labels also surface saved brief details when present:
goal, project type, target users, success criteria, stack preferences, first
milestone, and constraints. This lets new-project users verify the intended
product direction before scaffolding, and lets existing-project users verify
their saved intent before agents plan against the codebase.

Start/Nexus project-intake labels include the saved analysis date as
`updated: YYYY-MM-DD` / `갱신: YYYY-MM-DD`. Existing-project intake older than
14 days is also marked as stale and includes a `trinity project analyze <target>`
refresh command. This gives existing-project users a quick staleness check
before planning against a workspace that may have changed since the last
`trinity project analyze` or `trinity project status --refresh`.

For existing projects, Start/Nexus project-intake labels include the saved Git
state from the latest intake analysis. Non-Git workspaces show `git: none`, clean
repositories show the branch and clean state, and dirty repositories show saved
dirty and untracked counts. This keeps the selected project safety signal visible
before planning or execution. The same labels also surface detected source roots,
so existing-project users can confirm that Trinity found the expected source and
test directories before asking agents to plan against the project.

Execute preflight treats a dirty Git target, stale or sparse existing-project
intake, and incomplete new-project briefs as explicit safety gates. The first
`Confirm Execute` on a gated target shows a warning and keeps the preflight
modal open. Pressing `Confirm Execute` again confirms that the user wants to
execute anyway. Workspace selection mode is not gated, because selecting or
analyzing a target should remain read-only.

If an existing-project intake has no detected test commands, source roots, or
documentation, Start/Nexus and `project status` mark the analysis as sparse and
show the missing anchors: tests, source roots, and docs. This tells users that
Trinity has very little project structure to anchor the first plan and that
rerunning analysis after adding docs, source, or tests may improve agent
context.

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
