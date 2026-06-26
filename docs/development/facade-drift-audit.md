# Facade Drift Audit

This audit records the first post-CI-maintenance facade cleanup pass.

## Scope

Audited files:

- `src/trinity/workflow/engine.py`
- `src/trinity/orchestrator.py`
- `src/trinity/textual_app/app.py`

The cleanup only removed private methods that were:

- direct delegates to flow modules
- unused outside their own definition
- covered by existing workflow and required smoke tests

## Removed Private Delegates

Removed from `WorkflowEngine`:

- `_block_review_repair`
- `_apply_review_result_to_package`
- `_finalize_review_state`
- `_mark_post_review_items_done`

The authoritative behavior remains in:

- `WorkflowReviewFlow.block_review_repair`
- `WorkflowReviewFlow.apply_review_result_to_package`
- `WorkflowReviewFlow.finalize_review_state`
- `WorkflowPostReviewFlow.mark_items_done`

## Kept Facades

Public `WorkflowEngine` methods remain in place even when they delegate to a
flow. They are compatibility surface for callers and tests.

Private wrappers are also kept when either of these is true:

- another module still calls the wrapper
- the wrapper preserves a compatibility name used by tests
- the wrapper is a static helper re-export that still documents the old engine
  boundary

## Next Audit Pass

The next safe pass should inspect remaining private static helper re-exports in
`WorkflowEngine` after the corresponding flow modules have dedicated contract
docs. Current flow boundaries are summarized in
`docs/development/workflow-flow-contracts.md`. Do not remove public facade
methods without a migration note.
