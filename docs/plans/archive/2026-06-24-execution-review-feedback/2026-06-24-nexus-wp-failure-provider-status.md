# Nexus Work Package Failure Provider Status

## Problem

Nexus receives work-package completion events with `failed` or `blocked`
statuses, but the provider strip primarily relies on provider response events or
persisted response artifacts. When a provider execution fails without a fresh
agent-response event, the provider card can remain visually ready.

## Design

- Fold recent `WORK_PACKAGE_COMPLETED` events into provider snapshots.
- Only treat `failed` and `blocked` as provider issue states.
- Preserve existing successful provider state handling so normal completion does
  not overwrite richer response metadata.
- Use the work-package summary as the provider summary when available.

## Acceptance

- A recent failed work-package completion event marks the provider as `Error`.
- A recent blocked work-package completion event marks the provider as `Blocked`.
- Success completion events do not downgrade or overwrite the provider status.
