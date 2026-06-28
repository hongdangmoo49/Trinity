# Project Brief Target Display

## Problem

The project brief modal edits intake fields for the selected target workspace,
but the modal itself does not show that target. Users who launch Trinity from a
control repository and then select another workspace can lose confidence about
where the brief will be saved.

This affects both journeys:

- New project: the user wants to confirm the empty workspace that will receive
  the first plan.
- Existing project: the user wants to confirm the selected codebase before
  adding product intent.

## Scope

- Show the target workspace path near the top of `ProjectBriefModal`.
- Localize the label in English and Korean.
- Keep field ids, save behavior, intake persistence, readiness policy, and
  preflight gates unchanged.
- Keep target display read-only and informational.

## Design

`TrinityTextualApp._open_project_brief_modal` already receives the target path.
Pass that path into `ProjectBriefModal` as display metadata.

The modal renders:

- title
- target workspace row
- existing brief inputs
- actions

The target row should be visually muted and should not participate in the saved
`ProjectBriefDraft`.

## Tests

- Start `Analyze Existing` on an empty target opens the brief modal and shows
  the selected target path.
- Korean brief modal uses the localized target label.
