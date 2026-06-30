# Existing Project Analysis Start Prompt

Status: Superseded by the simplified Workbench flow. Start no longer seeds the
composer from a Workbench `Analyze Existing` action; the user's prompt is the
source of analysis/work intent.

## Problem

For an existing project, the Start screen `Analyze Existing` action writes a
project intake and refreshes the summary label. After that, the composer remains
empty, so first-time users still need to decide the next wording before Trinity
can begin useful planning.

That creates a handoff gap: Trinity has just analyzed the workspace profile, but
the primary prompt field does not reflect the obvious next action.

## Goals

- After Start `Analyze Existing` writes an existing-project intake, seed the
  Start composer with a concise default analysis prompt.
- Only seed the composer when it is empty.
- Do not overwrite a user-written prompt.
- Do not affect Nexus follow-up composition or execution preflight behavior.
- Do not seed the existing-project prompt when a picker selection is classified
  as a new-project candidate.

## Non-Goals

- Do not auto-submit the prompt.
- Do not add another modal or button.
- Do not change project-intake analysis contents.
- Do not change the new-project brief flow.

## Design

1. Route Start `Analyze Existing` picker completions through an
   analysis-specific callback instead of the generic workspace selection
   callback.
2. Reuse existing project-intake sync as the source of truth.
3. If the selected target is classified as `existing`, seed the Start composer
   with a localized default prompt:
   - English: analyze the existing project and propose next safe work packages.
   - Korean: analyze the existing project and propose the next work packages.
4. Skip seeding when the composer already contains user text.

## Tests

- Start `Analyze Existing` writes existing-project intake and seeds the default
  prompt.
- Start `Analyze Existing` preserves an already-written prompt.
- Existing focused Textual tests continue to cover picker behavior for control
  repo launches.
