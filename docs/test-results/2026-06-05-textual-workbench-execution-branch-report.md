# Textual Workbench Execution Branch Report

- Date: 2026-06-05
- Branch: `feature/textual-workbench-execution-analysis`
- Version: `0.10.2`
- Status: implemented

## Purpose

This document records the user-facing and runtime changes made on the
`feature/textual-workbench-execution-analysis` branch after the initial
Textual workbench implementation. It complements
`docs/plans/2026-06-05-textual-workbench-execution-analysis.md`, which is the
problem analysis document.

The branch focused on making the Textual workbench execute real Trinity
workflow work instead of only rendering static snapshots, and on fixing the
workspace preflight flow used before execution.

## Commit Summary

| Commit | Summary |
| :--- | :--- |
| `aac410f` | Added the initial Textual execution wiring analysis document. |
| `0ac2d0b` | Expanded workspace picker scope so sibling workspace folders can be selected. |
| `f366a00` | Added the Textual workflow controller and connected first prompt/follow-up execution. |
| `7a88e4c` | Hardened workflow completion polling so final state is not missed. |
| `3838912` | Allowed execute preflight to create missing target workspace directories. |
| `a4bebf6` | Projected central-agent round/synthesis runtime state and added activity indicators. |
| `e44ff77` | Added configurable missing-directory creation for execute preflight. |
| `4bb4c7c` | Added New Folder UX for selecting a new workspace folder from preflight. |
| `c2a8cb5` | Made New Folder create the directory immediately and cleaned up preflight labels. |
| `42ceeb1` | Bumped the patch version from `0.10.1` to `0.10.2`. |

## Screen Composition and Roles

### Start Screen

Primary role: collect the first user prompt and optionally select a target
workspace candidate before planning starts.

Current composition:

- Header with Trinity version.
- Intro/title block.
- Prompt composer for the first task request.
- Target workspace label.
- `Choose now` button.
- `Plan first` button.
- Footer key hints.

Behavior after this branch:

- `Choose now` opens the workspace picker using a broader tree root based on
  the Trinity control repo parent. This makes `/home/user/workspace` and
  sibling project folders reachable from the picker.
- `Plan first` starts a real workflow session through
  `TextualWorkflowController.start_prompt(...)`.
- The first prompt now becomes the workflow goal shown in Nexus.
- Provider work starts in the background instead of leaving provider cards in
  a static `Queued` state.

### Nexus Screen

Primary role: show planning progress, provider responses, central-agent
synthesis, user questions, workflow inspector data, and follow-up input.

Current composition:

- Three provider cards: Claude, Codex, Antigravity.
- Provider inspector button.
- `Execute` button.
- Central Agent panel.
- Workflow inspector panel.
- Bottom prompt composer for follow-up instructions and slash commands.

Behavior after this branch:

- Provider cards now reflect runtime events from the orchestrator:
  `Queued`, `Running`, `Ready`, or `Error`.
- Provider cards show a small activity frame while running.
- The central-agent panel now reads runtime deliberation events:
  `ROUND_START`, `CONSENSUS_CHECKING`, and `CONSENSUS_RESULT`.
- The first active deliberation round is displayed as round `1`, not round `0`.
- While provider responses are being collected, the central panel reports
  `round N collecting`.
- While synthesis is running, the central panel reports
  `round N synthesizing` and receives an activity indicator.
- Once synthesis completes, the central panel reports whether consensus was
  reached and includes fallback information when model-backed synthesis falls
  back to heuristic synthesis.
- If a later round starts after a previous non-consensus result, the central
  panel transitions to the new round's collecting state instead of showing the
  stale previous synthesis result.
- Follow-up text now flows through
  `TextualWorkflowController.submit_follow_up(...)`, so it can resume
  workflow state instead of only updating local UI text.

### Workflow Inspector

Primary role: summarize workflow metadata and runtime artifacts beside the
central agent.

Current composition:

- Workflow ID, state, and round.
- Questions summary.
- Decisions summary.
- Packages summary.
- Execution log summary.

Behavior after this branch:

- Inspector state now follows the controller snapshot, including runtime
  changes emitted during deliberation and completion polling.
- It no longer depends only on static startup snapshots.

### Execute Preflight Modal

Primary role: choose and validate the target workspace before execution.

Current composition:

- Target workspace path input.
- Directory tree rooted at a workspace-level parent, not only the Trinity
  control repository.
- Preflight summary panel.
- Bottom row with `New Folder` on the left and `Cancel` / `Confirm Execute`
  on the right.
- Status message row below the buttons.

Behavior after this branch:

- Existing writable directories can be selected from the tree or entered by
  path.
- Missing directories can be created when the selected path is creatable.
- `New Folder` asks whether to enable directory creation if creation is not
  already enabled.
- `New Folder` then opens a folder-name prompt.
- Submitting the folder name immediately creates the directory on disk.
- After creation, the path input, preflight panel, directory tree, and status
  message update immediately.
- The preflight panel no longer shows `Create supported`; that was an internal
  implementation detail and confused existing-path cases.
- `Confirm Execute` persists the selected target workspace and starts
  execution when the workflow is ready.

### Execution Matrix Screen

Primary role: show execution state after preflight approval.

Current composition:

- Header with target workspace path.
- Work-package table.
- Execution log panel.

Behavior after this branch:

- The screen receives snapshots from the same workflow controller used by
  Nexus.
- Execution updates are applied from controller polling, so the screen can
  reflect ongoing execution results after workspace preflight succeeds.

## Runtime Wiring

The main runtime addition is `TextualWorkflowController`.

Responsibilities:

- Archive stale active workflow sessions when the Textual app starts.
- Start a workflow from the first prompt.
- Run `TrinityOrchestrator.ask(...)` in a background worker.
- Attach a `TUIEventBus` and preserve recent runtime events.
- Convert persisted workflow state plus recent runtime events into
  `WorkflowNexusSnapshot`.
- Mark deliberation results back into `WorkflowEngine` after background work
  completes.
- Start execution after target workspace preflight has been confirmed.
- Continue polling while the worker is running or completion is pending.

## Verification

The branch was verified with focused tests and full regression runs during the
implementation.

Important checks:

- `uv run trinity --version` -> `trinity, version 0.10.2`
- `uv run pytest tests/test_textual_app.py tests/test_textual_workspace_picker.py -q`
- `uv run pytest tests/test_textual_snapshot.py tests/test_textual_workflow_controller.py -q`
- `uv run pytest tests/test_cli.py -q`
- `uv run pytest -q`

Latest full regression result at the time of the version bump:

```text
1086 passed, 1 warning
```

The remaining warning is the existing `AsyncMock` runtime warning in
`tests/test_error_handling.py`; it was not introduced by this branch.

## Notes and Remaining Watchpoints

- The Textual UI now drives real workflow work, but terminal-based provider
  behavior still depends on configured provider availability and transport
  mode.
- New Folder creation happens immediately after folder-name submission. Users
  should see the folder appear in the directory tree and external terminals
  before pressing `Confirm Execute`.
- Central-agent synthesis status is event-driven. If a provider never emits or
  synthesis times out, the fallback reason is now surfaced in the central
  summary when available.
