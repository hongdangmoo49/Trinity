# Project Mode Rail

## Problem

Start and Nexus now show target workspace, project-intake summary, analysis
anchors, anchor review, and new-project plan preview. These details are useful,
but users still need to infer the current journey state from several labels.

For both first-time and existing-project users, the Workbench should state the
current mode and next recommended action directly:

- no target selected
- intake not recorded
- target mismatch
- target missing
- new-project brief incomplete
- existing-project analysis stale/sparse/changed
- ready to plan or execute

## Scope

- Add a compact mode rail label shared by Start and Nexus.
- Derive the rail from saved project intake, selected target workspace, and the
  same read-only readiness signals already used by action variants.
- Render the rail on Start and Nexus near the project-intake controls.
- Refresh the rail from the existing `refresh_project_intake_summary()` paths.
- Keep prompt seeding, project-intake schema, workspace preflight, and action
  variant policy unchanged.

## Non-Goals

- Do not introduce a multi-step wizard.
- Do not block planning or execution.
- Do not run package managers, tests, or user code.
- Do not replace the detailed project-intake summary or plan preview labels.

## Design

Add `project_mode_rail_label()` to `textual_app/workspace_labels.py`.

The helper returns a concise localized string:

- English example: `Mode rail: existing | state: analysis changed | next: refresh analysis`
- Korean example: `모드 레일: 기존 | 상태: 분석 변경됨 | 다음: 분석 갱신`

It should follow the same priority as the current Workbench readiness:

1. No selected target and no intake: select or analyze a workspace.
2. Intake missing for selected target: analyze existing or create new.
3. Saved intake target mismatch: switch target or re-analyze.
4. Saved intake target missing: recover target.
5. New-project brief incomplete: edit brief.
6. Existing-project analysis sparse/stale/changed: refresh analysis.
7. Otherwise ready.

Start and Nexus mount one `Static` widget below project-intake actions. The
existing refresh method updates summary, mode rail, plan preview, and button
variants together.

## Tests

- Shared helper covers no intake, new brief missing, new ready, existing changed,
  target mismatch, and Korean output.
- Start refresh shows the rail after saving a new-project brief.
- Nexus refresh shows the rail after saving a new-project brief.
