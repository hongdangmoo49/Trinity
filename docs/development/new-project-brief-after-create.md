# New Project Brief After Create

Status: Superseded by the simplified Workbench flow. Workbench no longer
separates `Create New` from existing-project starts or opens `ProjectBriefModal`;
the selected workspace and user prompt now drive intent.

## Problem

Workbench now separates existing-project analysis from new-project creation, but
the new-project path still ends after the user creates or selects an empty
workspace. Trinity writes a `new` project intake and then relies on the user to
notice the separate `Edit Brief` action before agents receive enough product
intent.

That is a poor first-run path for a fresh project. For new workspaces, the next
natural step is to record the minimum product brief before planning or
execution.

## Goals

- When the user starts from `Create New` / `Create Project`, select or create a
  new workspace, and confirms the picker, open the project brief modal
  immediately.
- Keep `Select Workspace`, `Analyze Existing`, and execution preflight behavior
  unchanged.
- Keep the existing project-intake writer as the source of truth so Start,
  Nexus, CLI status, and provider prompts read the same state.
- Preserve the existing control-repo confirmation guard on Nexus before opening
  the brief modal.

## Non-Goals

- Do not add another modal or duplicate the brief form.
- Do not require a complete brief before the user can leave the modal.
- Do not treat normal workspace selection as new-project creation unless the
  user came through the explicit create-project action.

## Design

1. Route Start `Create New` through a create-specific workspace callback.
2. Route Nexus `Create Project` through the same create-specific behavior while
   retaining Nexus target-workspace synchronization and control-repo
   confirmation.
3. After the picker returns a `WorkspacePreflight`, sync project intake using the
   existing `created or new_project_candidate -> new` rule.
4. If the resulting selection is a new project, open `ProjectBriefModal` with
   `fallback_mode="new"`.
5. If the modal is cancelled, keep the incomplete `new` intake. Existing labels,
   button variants, prompt guidance, and execute gates continue to surface the
   missing brief state.

## Tests

- Start screen create-project flow creates a `new` intake and opens the brief
  modal after workspace confirmation.
- Nexus create-project flow creates a `new` intake, synchronizes the controller
  target workspace, and opens the brief modal after workspace confirmation.
- Focused Textual tests cover the behavior without changing execution preflight
  tests.
