# Nexus Analysis Follow-Up Prompt

Status: Superseded by the simplified Workbench flow. Nexus no longer seeds
follow-up prompts from a Workbench `Analyze Existing` path; the composer remains
user-authored.

## Problem

Start `Analyze Existing` now writes existing-project intake and seeds the Start
composer with a default analysis prompt. Nexus `Analyze Workspace` still writes
the intake only. The user remains in Nexus with an empty follow-up composer, so
the obvious next step is not connected to the analysis action.

## Goals

- After Nexus `Analyze Workspace` writes an existing-project intake, seed
  `#nexus-composer` with the existing-project analysis prompt.
- Only seed when the Nexus composer is empty.
- Preserve user-written follow-up text.
- Keep generic `Select Workspace`, new-project creation, project brief, and
  execute preflight behavior unchanged.
- Preserve the control-repo confirmation guard for picker-based Nexus analysis.

## Non-Goals

- Do not auto-submit the follow-up.
- Do not change project-intake analysis contents.
- Do not change Start behavior.

## Design

1. Route Nexus project-intake picker completions through an analysis-specific
   callback.
2. Reuse the existing Nexus workspace selection/apply behavior, then seed the
   composer only when the preflight is classified as `existing`.
3. Add a Nexus-specific existing-analysis prompt seed helper that checks route,
   mounted screen, target match, and empty composer before writing text.

## Tests

- Nexus `Analyze Workspace` writes existing-project intake and seeds the
  follow-up composer.
- Nexus `Analyze Workspace` preserves an already-written follow-up prompt.
