# Startup Provider Zero Selection Hint

## Problem

When no provider is selected, the startup provider CLI setup label currently
falls back to `found: none`. That is technically true, but it points at CLI
discovery instead of the actual recovery step: the user needs to select at least
one provider before planning or execution can start.

Provider selection is a prerequisite regardless of the selected workspace
context.

## Contract

When selected provider count is zero, render:

```text
Provider CLI setup: selected 0 | next: select at least one provider
```

Korean:

```text
프로바이더 CLI 설정: 선택 0개 | 다음: 프로바이더를 하나 이상 선택
```

When one or more providers are selected, keep the existing found/missing CLI
behavior.

## Non-Goals

- Do not change provider selection widgets.
- Do not auto-select a provider.
- Do not change submit-time validation.

## Test Plan

- Unit-test zero selected provider CLI setup labels in English and Korean.
- Keep existing found/missing CLI setup tests passing.
- Run focused Start screen tests and required smoke tests.
