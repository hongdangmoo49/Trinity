# Project Diagnostic Provider Selection Wording

## Problem

The project diagnostic readiness line says `providers 2 selected`. That number is
useful, but it can read like runtime provider readiness has already been checked.
In diagnostics, the line only knows how many enabled providers are selected. CLI
readiness is still checked by the provider readiness runtime when the workflow
starts.

For new and existing project onboarding, this distinction matters. A user should
not confuse "two providers selected" with "two providers are ready to run".

## Contract

Keep the checklist compact, but make the provider segment explicit:

```text
Readiness: target ok | context ok | providers 2 selected | validation planned
```

Korean:

```text
준비 상태: 대상 정상 | 컨텍스트 정상 | 프로바이더 2개 선택 | 검증 계획됨
```

## Non-Goals

- Do not run provider CLI readiness checks from diagnostic render paths.
- Do not add a modal or new provider setup flow.
- Do not change provider readiness runtime behavior.

## Test Plan

- Update project diagnostic readiness label tests for English and Korean copy.
- Update provider selection diagnostic tests.
- Run focused Start screen tests and required smoke tests.
