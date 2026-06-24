# Workflow outcome message i18n

Date: 2026-06-24
Branch: ux/workflow-outcome-message-i18n

## Problem

Textual Nexus already localizes most slash-command titles, tables, and static hints.
However, dynamic `TextualWorkflowOutcome.message` values from the workflow controller
are still shown in English in notifications and local command results.

This leaves Korean users with mixed-language feedback in common flows such as
execution preflight errors, retry requests, review start messages, resume results,
and post-review improvement errors.

## Scope

- Keep controller and workflow engine state messages unchanged.
- Add a presenter-level display helper that converts known outcome messages at the UI boundary.
- Apply the helper wherever `outcome.message` is displayed directly by `TrinityTextualApp`.
- Cover common exact and prefix-based workflow messages:
  - running/already-running guards
  - missing active agents
  - execution/retry/recovery messages
  - review and review-repair messages
  - resume messages
  - answer/improve/action messages surfaced through `WorkflowInputAction`
- Leave free-form summaries and generated content unchanged.

## Implementation Notes

The app still uses the original English message for control-flow checks such as
severity and recovery decisions. Only the rendered body/notification text changes.

## Verification

- Add focused presenter tests for Korean outcome message localization.
- Add Textual app tests for localized `/execute`, `/review`, `/improve`, `/answer`,
  and `/resume` result bodies.
- Run focused tests, Textual app tests, full test suite, diff check, and version check.
