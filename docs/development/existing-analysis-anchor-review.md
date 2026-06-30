# Existing Analysis Anchor Review

Status: Superseded by the simplified Workbench flow. `ProjectAnchorsModal` and
the Workbench `Analyze Existing` path were removed; existing-project analysis is
now expressed through CLI project-intake commands or the user's prompt.

## Problem

`Analyze Existing` can now detect concrete read, test, dev, and build anchors
and include them in the Start/Nexus seed prompt. The remaining gap is correction:
when the detected anchors are incomplete or wrong, users have no Workbench step
to review or adjust them before the prompt is seeded.

This matters most for existing projects because agent planning quality depends
on reading the right docs, source roots, and validation commands before editing.

## Scope

- Show a review modal after existing-project analysis when any anchor signal is
  detected.
- Let users edit detected docs, source roots, test commands, dev commands, and
  build commands as comma-separated values.
- Save the adjusted values back to the same project-intake JSON and Markdown
  artifacts.
- Seed the Start/Nexus composer with the adjusted anchors.
- If the user cancels, keep the detected intake and seed the prompt with the
  original detected anchors.
- Keep sparse existing-project analysis on the current no-modal path.
- Keep new-project brief, workspace selection, readiness, and preflight policy
  unchanged.

## Non-Goals

- Do not execute test/dev/build commands.
- Do not add a template resolver or project scaffolding behavior.
- Do not change the project-intake schema.
- Do not make anchor review a hard execution gate.

## Design

Add a small `ProjectAnchorsModal` under `textual_app/widgets/`. The modal owns
only presentation and input parsing. It receives an existing `ProjectIntake` and
returns a `ProjectAnchorsModalResult` containing either the adjusted anchor
values or a cancel signal.

The app layer remains responsible for persistence:

1. Build and write the detected existing-project intake as today.
2. If the intake has any anchor signal, open `ProjectAnchorsModal`.
3. On save, use `dataclasses.replace` to update the anchor fields, rewrite
   project-intake artifacts, refresh summary labels, and seed the Start/Nexus
   prompt with the adjusted intake.
4. On cancel, seed with the original detected intake.

This keeps detection read-only and keeps the modal free of filesystem writes.

## Tests

- Start `Analyze Existing` opens anchor review when anchors are detected and
  saving adjusted values updates intake and the seeded prompt.
- Start sparse existing analysis skips the modal and keeps the generic prompt.
- Nexus `Analyze Existing` opens the same review modal and uses adjusted anchors
  in the Nexus composer.
- Canceling anchor review keeps detected anchors and still seeds the prompt.
