# Execution Matrix I18n

## Problem

The Nexus execution flow now exposes retry actions in Korean UI mode, but the
Execution Matrix screen still renders English chrome such as `Expand Tasks`,
`Full Log`, `Retry`, `Activity`, and `Execution not started`.

## Design

- Pass the configured UI language into `ExecutionMatrixScreen`.
- Localize screen chrome only:
  - action buttons
  - matrix title and empty-state text
  - activity log heading and omitted-line hint
  - package header labels
- Preserve workflow data values such as package status, risk, owner, executor,
  and run ids.

## Acceptance

- Korean mode shows Korean execution matrix controls and activity labels.
- English mode keeps the previous labels.
- Existing execution matrix layout and retry behavior remain unchanged.
