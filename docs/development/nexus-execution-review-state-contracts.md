# Nexus Execution And Review State Contracts

This document records the current Nexus execution/review state projection
contract. Use it before changing `NexusSnapshotAdapter`, execution matrix UI,
review event emission, or retry/recovery display behavior.

## Scope

Authoritative implementation modules:

- `src/trinity/textual_app/snapshot.py`
  - `WorkflowNexusSnapshot`
  - `WorkPackageSnapshot`
  - `ReviewSnapshot`
  - `ExecutionRecoverySnapshot`
  - runtime review event projection
  - execution/review activity log formatting
- `src/trinity/textual_app/workflow_controller.py`
  - background execution/review run lifecycle
  - runtime event polling
  - execution failure and recovery surfacing
- `src/trinity/textual_app/screens/execution_matrix.py`
  - execution matrix summary
  - retry/recovery display
  - review lane display
- `src/trinity/workflow/execution.py`
  - `work_package_started`
  - `work_package_completed`
- `src/trinity/workflow/review_execution.py`
  - `review_package_queued`
  - `review_package_started`
  - `review_package_completed`
  - `review_package_skipped`
  - `work_package_review_started`
  - `work_package_review_completed`

## Source Priority

Nexus state is a read-only projection. It must not mutate workflow state while
rendering.

Projection inputs, in priority order:

1. Persisted `WorkflowSession`
   - current workflow state
   - work packages
   - execution results
   - review packages/results
   - execution run/recovery state
2. Persisted workflow event tail
   - execution log
   - review activity log
   - last recovery event
3. Recent in-memory `TUIEvent` values
   - live provider status
   - live work package progress
   - live review queued/started/skipped/completed state

Recent runtime events may refine display state before the persisted session is
fully updated, but they must not delete persisted evidence.

## Snapshot Stability

`WorkflowNexusSnapshot` is the stable UI contract for Nexus screens and report
surfaces. Execution/review work must preserve these fields:

- `state`
- `target_workspace`
- `providers`
- `work_package_details`
- `workflow_events`
- `execution_log`
- `execution_recovery`
- `final_review`
- `post_review_items`
- `supplemental_round`

`load_snapshot()` must remain side-effect free and cacheable. Cache keys must
include session file state, event file state, shared context fingerprint,
config-relevant values, and recent runtime event identity.

## Work Package Projection

`WorkPackageSnapshot` is the execution matrix row contract. It combines package
definition, current execution state, latest execution result, retry metadata,
review projection, and routing metadata.

Stable execution fields:

- `id`
- `title`
- `owner_agent`
- `status`
- `risk`
- `current_executor`
- `last_executor`
- `requires_execution`
- `dependencies`
- `expected_files`
- `acceptance_criteria`
- `parallel_group`
- `parallelizable`

Stable latest-result fields:

- `last_result_agent`
- `last_result_status`
- `last_result_summary`
- `last_result_files_changed`
- `last_result_blockers`
- `last_result_attempt_chain`

Stable retry/repair fields:

- `retryable`
- `retry_disabled_reason`
- `repair_attempt_count`
- `repair_max_attempts`
- `repair_blocked_reason`
- `repair_blocked_at`

Stable review projection fields:

- `review_status`
- `reviewer_agent`
- `review_summary`
- `review_required_changes`
- `review_severity`

## Runtime Execution Events

Execution event names are part of the UI log contract:

- `execution_run_started`
- `implementation_requested`
- `work_package_started`
- `work_package_completed`
- `execution_result_recorded`
- `execution_interrupted_detected`
- `execution_recovery_action`
- `work_package_retry_requested`
- `work_package_retry_skipped`

`work_package_started` must carry at least:

- `package_id`
- `agent`
- `status`

`work_package_completed` and `execution_result_recorded` must carry at least:

- `package_id`
- `agent`
- `status`
- optional `summary`

The activity log must prefer persisted completion events over duplicate
session-only execution result summaries when the event is visible in the tail.

## Review Projection

Review projection merges three views:

1. planned review packages
2. persisted review results
3. recent runtime review events

Runtime review event names are part of the UI contract:

- `review_package_queued`
- `review_package_started`
- `review_package_completed`
- `review_package_skipped`
- `work_package_review_started`
- `work_package_review_completed`

Runtime events must include enough identity to merge per package/reviewer:

- `package_id`
- `review_package_id` when available
- `reviewer_agent` or `reviewer`
- `target_agent` or `target`
- `status`
- `scope`
- optional `summary`
- optional `severity`
- optional `required_changes`
- optional `occurred_at`

Final review events and results must not be folded into per-work-package review
projection. Final review is represented separately as `final_review`.

## Review Status Precedence

Per-package review status must preserve this precedence:

1. terminal problem result: `failed`, `blocked`, `changes_requested`
2. live runtime review: `reviewing`
3. live queued review: `queued`
4. completed approved result: `approved`
5. all planned reviews skipped: `skipped`
6. workflow-state fallback: `reviewing` while session state is reviewing,
   otherwise `queued`

If a package has an approved result but planned review packages are not all
completed, Nexus must keep showing pending runtime/fallback status rather than
prematurely treating the whole package as approved.

## Reviewer Label Contract

Reviewer labels should include enough information to explain whether review is:

- planned but not started
- currently being reviewed
- skipped because no peer reviewer is available
- completed by one or more reviewers
- waiting for a second/escalated review

When provider count is one, peer review may be skipped. Nexus must show a
skipped/no-peer state rather than implying that review is still pending.

## Execution Recovery Snapshot

`ExecutionRecoverySnapshot` is shown when the execution run is:

- `running`
- `interrupted`
- `aborted`
- `failed`
- `repair_blocked`

It must remain hidden for a stale `running` execution run when the workflow
state is no longer `executing`.

Stable recovery fields:

- `run_id`
- `state`
- `target_workspace`
- `running_packages`
- `done_packages`
- `retry_candidates`
- `last_event`
- `last_event_at`
- `interrupted_reason`

The retry candidate set is derived from executable packages with status
`running`, `blocked`, or `failed`. Done packages must not be retryable.

## Execution Matrix Display Contract

The execution matrix summary must count packages by compact execution status:

- running
- waiting
- done
- issue
- review

Review-pending packages should count as review rather than done. Recovery retry
count must use the larger of package-level retryable count and recovery retry
candidate count.

The execution matrix target workspace should prefer:

1. preflight-selected path
2. snapshot target workspace
3. recovery target workspace

## Controller Contract

`TextualWorkflowController.drain_updates()` is the bridge from background runs
to persisted workflow state. It must:

- append execution progress results before completion finalization
- record final execution results on execution completion
- surface execution recovery when execution fails and retryable packages exist
- auto-start review after execution only when configured and review is pending
- record review results before preparing repair execution
- set `execution_recovery_required` when UI should show retry/recovery actions

Background runtime events are recent-event hints. Persisted workflow state
remains the source of truth after completion is drained.

## Focused Test Guidance

Use these tests for Nexus execution/review state changes before required smoke:

```bash
uv run pytest -q \
  tests/test_textual_snapshot.py \
  tests/test_textual_workflow_controller.py \
  tests/test_execution_matrix_state_cache.py \
  tests/test_execution_retry_modal.py \
  tests/test_central_agent_view.py \
  tests/test_review_execution_protocol.py \
  tests/test_execution_protocol.py
uv run python scripts/run_required_smoke_tests.py -q
```
