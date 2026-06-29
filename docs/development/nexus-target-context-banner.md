# Nexus Target Context Banner

Date: 2026-06-29
Branch: `feature/nexus-target-context-banner`

## Problem

Nexus already shows the selected workspace in the action bar, but the central
conversation can still feel detached from that target. When a user launches
Trinity from one repository and selects another target workspace, the central
agent response may visually look like it belongs to the launch repository.

This is especially confusing for existing-project onboarding because the user's
main question is whether Trinity is discussing the selected project, not the
control repository.

## Proposed UX

When the workflow snapshot has a target workspace, the Central Agent markdown
should show a stable target context line near the top:

```text
Progress: ...
Target workspace: /home/user/workspace/msu
```

Korean:

```text
진행: ...
대상 작업 폴더: /home/user/workspace/msu
```

This keeps the current project visible next to the synthesis and goal, even when
the action bar scroll position or central response body changes.

## Scope

- Add a target workspace line to `CentralAgentView._markdown()`.
- Localize the label in English and Korean.
- Keep the existing action bar workspace label unchanged.
- Do not load project intake from the widget in this slice; only render the
  workflow snapshot target.

## Validation

- Add focused `CentralAgentView` markdown tests.
- Run:
  - `uv run pytest tests/test_central_agent_view.py -q`
  - `uv run python scripts/run_required_smoke_tests.py -q`
