# Startup Provider CLI Setup Hint

## Problem

The Start and Nexus screens now show how many providers are selected, but a
first-time user can still discover a missing CLI only after starting the
workflow. That is especially painful when beginning a new project or onboarding
Trinity into an existing project, because the first action appears ready but the
provider cannot launch.

Provider readiness runtime already performs the full check later. The startup
screen should not duplicate that expensive or side-effect-prone flow.

## Contract

Add a lightweight setup hint below the provider policy:

```text
Provider CLI setup: selected 2 | found: claude | missing: codex
```

Korean:

```text
프로바이더 CLI 설정: 선택 2개 | 발견: claude | 없음: codex
```

Rules:

- Only inspect selected, enabled providers.
- Check whether each provider's configured `cli_command` resolves to an
  executable path or PATH entry.
- Do not run provider CLIs.
- Do not discover models.
- Do not perform auth, workspace trust, or permission checks.
- Use the provider readiness runtime as the source of truth once a workflow
  starts.

## UX Notes

This hint is intentionally named `CLI setup`, not `readiness`, because finding
an executable does not prove that the provider can answer. It only catches the
most common first-run setup miss early.

## Test Plan

- Unit-test found, missing, mixed, and zero selected provider CLI labels.
- Render-test Start and Nexus to confirm the label updates when provider
  selection changes.
- Run focused Start screen tests and required smoke tests.
