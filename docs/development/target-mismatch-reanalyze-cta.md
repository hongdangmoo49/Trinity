# Target Mismatch Reanalyze CTA

Status: Superseded by the simplified Workbench flow. Workbench no longer shows
`Analyze Existing` CTA copy; target mismatch remains a project-intake/status
signal.

## Context

Start and Nexus already detect when persisted project intake belongs to a
different target workspace than the currently selected workspace. The state label
and mode rail mention the mismatch, but the primary analyze button still uses the
generic "Analyze Existing" copy.

For users switching from one project to another, this weakens the next action:
the right action is not generic analysis, it is re-analyzing the currently
selected workspace so prompt context and UI state stop referring to the old
target.

## Goal

Make the mismatch recovery CTA explicit on Start and Nexus.

## Scope

- Add a dedicated analyze-action label key for target mismatch.
- Use that label when saved intake target differs from the selected workspace.
- Keep the button variant as warning for mismatch.
- Add English and Korean labels.
- Add label helper and mounted screen tests.

## Non-goals

- Do not change project intake persistence.
- Do not auto-run analysis.
- Do not change target selection or workspace picker behavior.
- Do not change prompt-context guard behavior.

## Expected Behavior

- Matching target: existing analyze/refresh labels remain unchanged.
- Missing target intake with selected workspace: use the existing warning flow.
- Mismatched target: button label becomes "Analyze Selected" / "선택 대상 분석".

## Test Plan

- Unit test `project_analyze_action_presentation` returns the mismatch label key
  and warning variant.
- Mount Start and Nexus with mismatched intake and verify the button label.
- Run required smoke tests before version bump and PR.
