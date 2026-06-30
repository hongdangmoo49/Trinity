# Project Start Choice Guide

Date: 2026-06-29
Branch: `feature/project-start-choice-guide`
Status: Superseded by the simplified Workbench flow. Start/Nexus no longer show
project-start guide lines or separate existing/new action buttons; workspace
selection plus prompt intent is the current model.

## Problem

Start and Nexus now expose the core onboarding controls:

- Select Workspace
- Analyze Existing
- Create New
- Complete/Edit Brief
- Plan first / Execute

The controls are useful, but a first-time user still has to infer that Trinity
supports two different project starts:

- connect and analyze an existing project;
- create and brief a new project.

This is most visible when a user opens Trinity with no recorded project intake.
The screen shows several actions, but it does not explicitly say which action
starts which journey.

## Proposed UX

Add a compact project-start guide line on Start and Nexus:

```text
Project start: existing -> Analyze Existing | new -> Create New | then Plan first
```

Korean:

```text
프로젝트 시작: 기존 -> 기존 프로젝트 분석 | 신규 -> 새 프로젝트 생성 | 이후 먼저 계획
```

When a project intake is already recorded, the line should keep the same shape
but include the recorded mode:

```text
Project start: mode existing | next -> Analyze Existing / Refresh Analysis
```

This keeps the onboarding choice visible without changing button behavior or
workflow state transitions.

## Scope

- Add a pure presenter function for the guide label.
- Render it on Start and Nexus near the project intake actions.
- Localize English and Korean labels.
- Keep all existing actions and workflow messages unchanged.

## Validation

- Add focused presenter/screen tests.
- Run:
  - `uv run pytest tests/test_start_screen.py -q`
  - `uv run python scripts/run_required_smoke_tests.py -q`
