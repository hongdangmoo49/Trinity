# Direct Analyze New Brief Handoff

Status: Superseded by the simplified Workbench flow. Start/Nexus no longer
route `Analyze Existing` into project-intake sync or `ProjectBriefModal`; the
Workbench keeps workspace selection separate from prompt intent.

## Problem

The picker path for `Analyze Existing` now opens the project brief modal when
the selected workspace is an empty new-project candidate. The direct path still
uses only `safe_start_target_workspace`. If Trinity was launched from an empty
workspace and the user presses `Analyze Existing`, the app can write an
`existing` intake for a new project candidate.

That makes the direct path disagree with Workspace Preflight and hides the
new-project brief recovery step.

## Goals

- Use Workspace Preflight classification before writing direct Start/Nexus
  project intake.
- When a direct `Analyze Existing` target is a new-project candidate, write
  `new` intake and open the project brief modal.
- Keep existing-project direct analysis unchanged: write existing intake and
  seed the existing-analysis prompt.
- Keep picker, `Create New`, direct brief edit, and execute preflight behavior
  unchanged.

## Non-Goals

- Do not rename `Analyze Existing`.
- Do not auto-submit prompts.
- Do not change the empty-directory classification rule.

## Design

1. Build a read-only `WorkspacePreflight` for direct Start/Nexus analysis
   targets.
2. Reuse `_project_intake_mode_for_preflight`.
3. If the mode is `existing`, keep the current prompt seed behavior.
4. If the mode is `new`, sync new intake and open `ProjectBriefModal` with
   `fallback_mode="new"`.

## Tests

- Start direct `Analyze Existing` from an empty launch target opens the brief
  modal and writes `new` intake.
- Nexus direct `Analyze Existing` from an empty launch target opens the brief
  modal and writes `new` intake.
