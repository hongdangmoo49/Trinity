# Execution Risk Confirmation Gate

Date: 2026-06-29
Branch: `feature/execution-risk-gate`

## Problem

Nexus execution confirmation currently shows the target workspace, project mode,
providers, and work package preview. It does not surface the same risk signals
that the workspace preflight already knows about:

- dirty Git workspace
- stale or changed existing-project intake
- sparse existing-project intake
- incomplete new-project brief

Users can therefore press Execute from Nexus and see a confirmation modal that
looks safe even when the target has risk signals.

## Goal

Add execution risk visibility to the Nexus execution confirmation modal.

## User Experience

1. User clicks Execute from Nexus.
2. Trinity opens the execution confirmation modal.
3. The modal shows existing summary fields plus a risk section.
4. If no risks are present, the risk section says "none".
5. If risks are present, the modal lists concise reasons before the package
   preview, so confirmation is deliberate.

## Implementation Plan

- Reuse `build_preflight` to compute risk signals for the selected execution
  target.
- Extend `ExecutionConfirmationSummary` with `risk_items`.
- Add localized risk labels to the execution confirmation modal.
- Keep the existing confirm/cancel behavior; this slice improves visibility
  without adding another blocking modal.
- Add tests for clean and risky execution summaries.

## Non-Goals

- Do not execute git or test commands.
- Do not add a new multi-step confirmation flow in this slice.
- Do not remove the existing workspace picker double-confirm behavior.

## Success Criteria

- Execution confirmation shows "Risks: none" for clean execution.
- Execution confirmation lists dirty workspace and intake safety warnings when
  present.
- Existing confirmation behavior still works.
- Tests and required smoke pass.
