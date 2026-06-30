# Nexus Project Next Action

Date: 2026-06-29
Branch: `feature/nexus-project-next-action`
Status: Superseded by the simplified Workbench flow. Nexus no longer exposes
`Continue Setup` or individual project setup buttons; execution remains a
workflow action, while project intent comes from the prompt.

## Problem

The Start screen now has a `Continue Setup` button that routes users to the
next safe project onboarding action. Nexus still shows the same individual
project actions, but it lacks a single "continue the project setup" action.

Users can reach Nexus directly from a restored session or after a partial
workflow, so the same next-action affordance should exist there too.

## Proposed UX

Add a `Continue Setup` button to the Nexus project-intake action row. It routes
to existing Nexus events:

- no effective target workspace -> `WorkspaceRequested`
- target selected but no matching intake -> `ProjectIntakeRequested`
- new-project intake with missing target -> `NewProjectRequested`
- new-project intake with incomplete brief -> `ProjectBriefRequested`
- existing-project intake requiring refresh or scope review -> `ProjectIntakeRequested`
- otherwise -> `ExecuteRequested`

This mirrors Start behavior while using Nexus's execution affordance as the
ready-state continuation.

Korean label:

```text
설정 계속
```

## Scope

- Add the Nexus-only button and localized label.
- Add a small routing helper on `NexusScreen`.
- Reuse existing messages.
- Do not change Start behavior in this slice.

## Validation

- Add focused Nexus screen tests for the routing helper.
- Run:
  - `uv run pytest tests/test_start_screen.py tests/test_nexus_workspace_candidate_cache.py -q`
  - `uv run python scripts/run_required_smoke_tests.py -q`
