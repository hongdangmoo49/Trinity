# New Project Generation Confirmation

## Background

New-project onboarding now records enough brief data to show a generation
preview: likely files/folders, validation commands, and guardrails. The preview
appears on Start/Nexus after saving a brief, but a user can still start planning
without explicitly confirming that this is the intended first project shape.

There is also a subtle state boundary: starting a workflow from Start should not
rewrite a saved `new` project intake as `existing` just because a target
workspace is present.

## Goal

- Before Start begins planning from a complete new-project intake, show a
  focused confirmation modal.
- Show target workspace, generation preview, and validation plan.
- Only call `workflow_controller.start_prompt()` after confirmation.
- Preserve a matching saved `new` project intake when starting the workflow.

## Trigger

Show the modal when all are true:

- current route is Start
- target workspace is selected
- saved project intake matches the target
- saved intake mode is `new`
- required new-project brief fields are complete
- generation preview text is available

Cancel keeps the user on Start without mutating workflow state. Confirm follows
the existing Start submission path.

## Scope

- Add a small modal and pure summary helper.
- Route Start prompt submission through the confirmation when eligible.
- Keep Nexus follow-up and `/execute` confirmation unchanged.
- Use the same generated preview/validation formatter already shown in Start
  and Nexus labels.

## Non-goals

- Do not generate files directly.
- Do not change work package planning.
- Do not block users with incomplete new-project briefs in this slice; the
  existing brief-completion CTA continues to guide that case.
- Do not change existing-project planning.

## Validation

- Unit tests for confirmation summary formatting.
- App tests proving Start does not call the controller until confirm.
- App tests proving cancel leaves the workflow untouched.
- App test proving a saved `new` intake remains `new` after confirmed Start.
- `uv run python scripts/run_required_smoke_tests.py -q`
