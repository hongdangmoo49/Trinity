# Existing Analysis Target Prompt

Status: Superseded by the simplified Workbench flow. Start/Nexus no longer
generate target-aware analysis prompts from `Analyze Existing`; the visible
workspace label supplies the target and the user prompt supplies intent.

## Problem

`Analyze Existing` seeds a generic prompt. The workflow target is set
separately, but the visible prompt does not name the selected workspace or make
the existing-project safety expectation explicit. For users switching between a
Trinity control repo and another target project, that can make the UI feel like
it may still analyze the launch directory.

## Scope

- Include the selected target workspace path in the seeded existing-project
  analysis prompt.
- Tell agents to read existing docs/source/test signals before proposing work.
- Explicitly avoid new-project scaffolding language for non-empty existing
  workspaces.
- Keep Start and Nexus behavior aligned.
- Do not change project-intake persistence, target selection, preflight, or
  provider prompt contracts.

## Design

Change `_existing_project_analysis_prompt` so it accepts an optional `target`
path. Start/Nexus existing analysis seed paths already know the selected target,
so they pass it directly.

Prompt shape:

- English: analyze the selected existing project at `<path>`, inspect existing
  anchors first, then propose safe work packages.
- Korean: same guidance with localized wording.

If a future caller does not have a target path, the helper should still return a
target-less safe prompt.

## Tests

- Start `Analyze Existing` seeds a prompt containing the selected path and
  existing-project safety guidance.
- Nexus `Analyze Existing` seeds the same target-aware prompt.
