# Startup Provider CLI Short Recovery Hint

## Problem

The missing-provider CLI recovery hint is actionable, but the phrase
`install CLI or update cli_command/PATH` is long for a compact status notice.
After capping missing entries, the recovery text is now the widest remaining
fixed segment.

## Contract

Use a shorter phrase while preserving the same meaning:

```text
next: fix CLI command/PATH
```

Korean:

```text
다음: CLI 명령/PATH 수정
```

This still points users to the two recovery paths: install/fix the executable or
update Trinity's configured `cli_command`.

## Non-Goals

- Do not add provider-specific install instructions.
- Do not change CLI probing or readiness behavior.
- Do not change zero-provider selection guidance.

## Test Plan

- Update provider CLI setup unit/render tests for the shorter phrase.
- Run focused Start screen tests and required smoke tests.
