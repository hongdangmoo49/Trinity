# Final Review Auto Replan

Date: 2026-06-11

Branch: `feature/final-review-auto-replan`

Status: implementation in progress

## Goal

When final review requests concrete changes, Trinity should not stop at
`POST_REVIEW_READY` and wait for the user to type `/improve high`. The central
workflow engine should convert required final-review changes into supplemental
work packages automatically, then return the workflow to `BLUEPRINT_READY` so
the user can execute the new work.

## Prior Behavior

`WorkflowEngine.finalize_post_review()` normalized review findings into
`PostReviewActionItem` records and always moved the workflow to
`POST_REVIEW_READY`.

For `CHANGES_REQUESTED`, the user then had to run one of:

- `/improve high`
- `/improve all`
- `/improve AI-001`

Only after that did Trinity append `WP-S###` supplemental packages.

## New Behavior

For final review results with `ReviewStatus.CHANGES_REQUESTED`:

1. Extract post-review action items as before.
2. Select newly created final-review action items that are required execution
   work:
   - `bugfix`
   - `validation`
3. If a target workspace exists, automatically accept those action items.
4. Append supplemental `WP-S###` work packages.
5. Mark the execution run as `supplemental_queued`.
6. Set the execution run source to `final_review_auto_replan`.
7. Move the workflow to `BLUEPRINT_READY`.

The workflow does not automatically execute the new packages. The user still
decides when to run `/execute`.

## Guardrails

Automatic replanning is skipped when:

- final review is not `CHANGES_REQUESTED`;
- no required final-review action items were created;
- the target workspace is not selected.

When skipped because the target workspace is missing, Trinity records a
`post_review_auto_replan_skipped` event and keeps the workflow in
`POST_REVIEW_READY`.

## Why This Shape

This keeps the workflow proactive without making file changes automatically.
The central agent prepares the next work package plan, while execution remains a
separate user-confirmed step.

## Validation

- Engine test: final-review required changes queue `WP-S001` immediately.
- Engine test: missing target workspace preserves the old user-decision flow.
- Textual controller test: auto-queued supplemental work is visible without
  calling `/improve`.
- Plain TUI test: final review changes immediately produce queued supplemental
  work.
