# Start Project Next Action

Date: 2026-06-29
Branch: `feature/start-project-next-action`
Status: Superseded by the simplified Workbench flow. Start no longer exposes
`Continue Setup`, `Analyze Existing`, `Create New`, `Edit Brief`, or `Plan first`
buttons; Enter on the prompt is the primary action.

## Problem

The Start screen now explains the new/existing project paths with a
`Project start` guide, but users still need to choose among several buttons:

- Select Workspace
- Analyze Existing
- Create New
- Complete/Edit Brief
- Plan first

For a first-time user, the safest next step can already be derived from the
current project context. The UI should provide one compact "do the next project
setup step" action without removing the explicit buttons.

## Proposed UX

Add a `Continue Setup` button to the Start project-intake action row. It routes
to existing Start events:

- no target workspace -> `WorkspaceRequested`
- target selected but no matching intake -> `ProjectIntakeRequested`
- new-project intake with missing target -> `NewProjectRequested`
- new-project intake with incomplete brief -> `ProjectBriefRequested`
- otherwise -> submit the current prompt like `Plan first`

This keeps the user's escape hatches visible while making the obvious next
project-start action one click.

Korean label:

```text
설정 계속
```

## Scope

- Add the Start-only button and localized label.
- Add a small routing helper on `StartScreen`.
- Reuse existing messages and submission behavior.
- Do not change Nexus in this slice.

## Validation

- Add focused Start screen tests for the routing helper.
- Run:
  - `uv run pytest tests/test_start_screen.py -q`
  - `uv run python scripts/run_required_smoke_tests.py -q`
