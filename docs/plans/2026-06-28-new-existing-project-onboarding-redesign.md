# New And Existing Project Onboarding Redesign

Date: 2026-06-28
Branch: `docs/new-existing-project-onboarding-redesign`

## Problem

Trinity currently treats new projects and existing projects as the same entry
flow. `trinity init` creates `.trinity/` in the current directory, and the
Textual Start/Nexus screens expose a target workspace picker, but the user is
not asked which project journey they are starting.

This creates ambiguity:

- A new-project user needs a folder creation and kickoff context flow.
- An existing-project user needs read-only analysis, git safety, and target
  workspace certainty before planning or execution.
- A user running `trinity` from the Trinity control repo can accidentally prompt
  agents about the control repo even after selecting another workspace.
- Workspace preflight currently shows `dirty worktree` as unknown, which is weak
  for existing-project execution safety.

## User Journeys

### New Project

Goal: help the user create a target workspace and seed enough context for
planning before any provider writes files.

Expected flow:

1. User runs `trinity init` or opens the Start screen.
2. Trinity offers "New project" as an onboarding mode.
3. User chooses a parent folder and project name.
4. Trinity creates or confirms the target workspace.
5. Trinity optionally records project type, stack hints, constraints, and first
   goal into an intake document.
6. Planning starts with explicit target workspace context.

### Existing Project

Goal: help the user connect a real repository safely and make agents talk about
that repository, not the control repo.

Expected flow:

1. User runs `trinity init` inside or near an existing project, or opens the
   Start/Nexus workspace picker.
2. Trinity offers "Existing project" as an onboarding mode.
3. User selects the target workspace.
4. Trinity runs a read-only project preflight:
   - path exists and is writable
   - git repository detection
   - branch detection
   - dirty and untracked file counts
   - package manager or manifest hints
   - likely test command hints
5. Trinity stores this as project intake context.
6. Start/Nexus clearly display the selected target workspace and its read-only
   analysis status before planning or execution.

## Proposed Product Surface

### CLI

Add explicit entry points after the first implementation slice:

- `trinity init --mode new`
- `trinity init --mode existing`
- `trinity project analyze [PATH]`

Default interactive `trinity init` should ask for the mode when stdin/stdout are
interactive. Non-interactive init can keep the current default until the mode
contract is stable.

### Textual Start/Nexus

Add a lightweight project-mode surface:

- Start screen workspace label should distinguish:
  - `Planning target: <path>`
  - `No target workspace selected`
  - `Control repo selected; confirmation required before write`
- Nexus action bar should show target workspace and analysis status in the same
  row as Select Workspace/Execute.
- Workspace picker should make "new folder" and "existing repo" intent explicit.

### Project Intake Artifact

Use Trinity state, not the user repo, for generated intake files:

- `.trinity/project-intake.json`
- `.trinity/project-intake.md`

Initial fields:

- `mode`: `new` or `existing`
- `target_workspace`
- `created_at`
- `git_repo`
- `branch`
- `dirty_count`
- `untracked_count`
- `package_managers`
- `test_commands`
- `notes`

The markdown file should be safe to include in deliberation prompts.

## First Implementation Slice

Implement workspace preflight git safety metadata first. This is low risk and
immediately useful for existing-project users.

Scope:

- Replace `dirty worktree: unknown` in the Textual workspace preflight with a
  computed value when the target is a git repo.
- Keep behavior read-only.
- Do not block execution yet; display only.
- Add tests for clean, dirty, untracked, and non-git paths.

Suggested implementation files:

- `src/trinity/textual_app/widgets/workspace_picker.py`
- `tests/test_textual_workspace_picker.py`

Validation:

- `uv run pytest -q tests/test_textual_workspace_picker.py`
- `uv run python scripts/run_required_smoke_tests.py -q`

## Later Slices

1. Project intake data model and file writer.
2. `trinity project analyze [PATH]` command.
3. Start/Nexus target workspace wording update.
4. Interactive `trinity init` project mode prompt.
5. New-project folder creation and optional `git init`.
6. Inject project intake summary into deliberation and follow-up prompts.

## Non-Goals

- Do not relax target workspace write guards.
- Do not let Trinity write project intake files into the target workspace by
  default.
- Do not require users to select a target workspace before planning; planning
  should still work, but the selected target must be explicit when present.
- Do not make provider auth/bootstrap part of project mode selection.

## Success Criteria

- A new user can tell whether Trinity is creating a new target project or
  connecting to an existing one.
- An existing-project user sees repository safety facts before execution.
- Agents receive target workspace context when it exists.
- The Trinity control repo and user target workspace remain visually and
  operationally distinct.
