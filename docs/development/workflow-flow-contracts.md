# Workflow Flow Contracts

This document records the current `WorkflowEngine` facade contract after the
flow-module extraction work. Use it before removing additional wrappers from
`src/trinity/workflow/engine.py`.

## Scope

Authoritative implementation modules:

- `WorkflowInputFlow`: plain input routing by workflow state
- `WorkflowLifecycleFlow`: start, blueprint continuation, execution enablement
- `WorkflowDeliberationResultFlow`: completed deliberation result state
  transitions, provider metadata observation, provider error gate entry, and
  blueprint application
- `WorkflowQuestionFlow`: open-question resolution and user decisions
- `ProviderErrorGateFlow`: retry, continue, or stop after provider failures
- `WorkflowWorkspaceFlow`: target workspace selection
- `WorkflowCentralFlow`: central transcript records and continuation prompts
- `WorkflowExecutionFlow`: execution run lifecycle and package status updates
- `WorkflowReviewFlow`: peer review planning, review result recording, repair
  loop entry
- `WorkflowPostReviewFlow`: final-review follow-up and supplemental packages
- `ExecutionRecoveryFlow`: interrupted execution retry or abort handling
- `WorkflowQualityFlow`: advisory execution/review quality summaries
- `WorkflowCollectionFlow`: list-backed lookup and upsert helpers
- `WorkflowLedgerSync`: shared ledger rendering and persistence
- `WorkflowPersistenceFlow`: session save, event append, timestamp normalization,
  and initial session load/create

`WorkflowEngine` remains the public compatibility facade. Public engine methods
may delegate to a flow, but callers should not import flow classes directly
unless they are tests for that flow.

## Shared Invariants

All flows mutate `engine.session` and persist events through
`engine._persistence_flow().persist()`. Changes that affect user-visible state
must update `session.updated_at` and emit an event with enough data for report
reconstruction.

State transitions must go through `engine.set_state()`. Flow methods should not
assign `session.state` directly.

Methods that return a user-input decision must return
`WorkflowEngine.input_action_type` (`WorkflowInputAction` by default). This
keeps Textual, slash commands, and tests on the same routing contract.

Targeted provider calls must use `WorkflowTargetingFlow.effective_target_agents()`
and `WorkflowTargetingFlow.normalized_model_overrides()` so one-provider,
two-provider, and targeted agent UX stay consistent. Work package decomposition
must use `WorkflowTargetingFlow.decomposition_agents()` when active
`AgentSpec` metadata is available.

## Facade Surface

Keep these `WorkflowEngine` public methods as compatibility surface unless a
release note and migration path exist:

- input and lifecycle: `handle_user_input()`, `start()`,
  `continue_from_blueprint()`, `enable_execution_for_current_blueprint()`
- questions: `answer_pending_question()`, `answer_question()`,
  `answer_question_option()`, `resolve_question()`, `add_open_question()`
- workspace: `set_target_workspace()`, `clear_target_workspace()`
- central result handling: `mark_deliberation_result()`
- execution: `pending_execution_package_ids()`, `begin_execution()`,
  `record_work_package_started()`, `record_work_package_completed()`,
  `plan_parallel_groups()`, `record_execution_batch_planned()`,
  `record_execution_results()`
- review: `ensure_review_packages()`, `review_packages_for_request()`,
  `record_review_results()`, `prepare_review_repairs()`,
  `reconcile_review_repair_metadata()`, `review_repair_blocked_package_ids()`,
  `accept_review_repair_blocks()`, `stop_review_repair_blocks()`
- post-review: `finalize_post_review()`, `extract_post_review_items()`,
  `handle_post_review_input()`, `accept_post_review_items()`,
  `queue_supplemental_work_packages()`, `post_review_summary()`
- recovery: `detect_interrupted_execution()`, `execution_recovery_summary()`,
  `build_execution_retry_plan()`, `prepare_execution_retry()`,
  `retry_interrupted_execution()`, `mark_interrupted_execution()`,
  `abort_interrupted_execution()`
- reporting and persistence: `render_shared_ledger()`, `sync_shared_ledger()`,
  `save()`

Private direct delegates may be removed only when no module imports or calls
them and focused flow tests plus required smoke cover the behavior.

## Flow Contracts

### Input And Lifecycle

`WorkflowInputFlow.handle_user_input()` is the only plain-text router. It must
route by current state in this order:

1. `POST_REVIEW_READY` to post-review follow-up handling.
2. `NEEDS_USER_DECISION` to question answering.
3. Existing blueprint continuation for blueprint-ready, reviewing, done, or
   failed workflows.
4. New workflow start.

`WorkflowLifecycleFlow.start()` creates a new `WorkflowSession`, preserves an
idle preselected target workspace, persists `workflow_started`, transitions to
`DELIBERATING`, and returns a deliberation action.

`enable_execution_for_current_blueprint()` requires an approved blueprint,
active agents, and a selected target workspace. It regenerates executable work
packages, clears execution/review history for the execution round, persists
`execution_enabled`, and returns an execution-requested action.

### Questions And Provider Error Gate

`WorkflowQuestionFlow.answer_question()` records a `DecisionRecord`, keeps the
workflow in `NEEDS_USER_DECISION` while more open questions remain, and resumes
deliberation only after the blocking question set is clear.

Completed deliberation results are applied by `WorkflowDeliberationResultFlow`.
It records provider metadata, opens the provider error gate before blueprint
application when retryable provider failures exist, then applies structured
consensus or consensus fallback.

Provider error gate questions are resolved by `ProviderErrorGateFlow`, not by
ordinary deliberation continuation:

- `retry` returns a targeted deliberation action for failed providers.
- `continue` marks the stored deliberation result and bypasses failed providers
  only when a usable consensus exists.
- `stop` transitions the workflow to `FAILED`.

Provider readiness and recovery details are tracked in
`docs/development/provider-readiness-recovery-contracts.md`.

### Workspace

`WorkflowWorkspaceFlow.set_target_workspace()` resolves the path, records
whether the Trinity control repo was explicitly confirmed as target, and emits
`target_workspace_selected` through `WorkflowPersistenceFlow`.

Execution and post-review improvement must require a selected target workspace
before provider write operations are requested.

### Execution

`WorkflowExecutionFlow.begin_execution()` requires at least one executable work
package and a selected target workspace. It creates a new `execution_run`, emits
`execution_run_started` and `implementation_requested`, then transitions to
`EXECUTING`.

Package start and completion updates must keep `current_executor`,
`last_executor`, `execution_run.heartbeat_at`, and event history in sync.

`record_execution_results()` is responsible for appending execution results,
recording quality signals, upserting subtasks, and finalizing execution state.
Execution state finalization may enter review preparation, retry/recovery, or a
terminal state depending on package statuses.

### Review And Repair

`WorkflowReviewFlow.ensure_review_packages()` is idempotent for a session with
existing review packages. It plans required peer reviews for reviewable work
packages and excludes already approved review targets.

`record_review_results()` appends typed `ReviewResult` values, records quality
signals, and finalizes review state unless the caller disables finalization.

`prepare_review_repairs()` converts requested changes into pending repair work
only when the package is executable, under the retry limit, and not a duplicate
repair signature. Blocked repair decisions are persisted for explicit accept or
stop handling.

### Post-Review

`WorkflowPostReviewFlow.finalize_post_review()` extracts final-review action
items and either auto-replans required changes or transitions to
`POST_REVIEW_READY`.

`handle_post_review_input()` handles `/improve` style selection, free-text
follow-up creation, and `/improve done`. It must not start a new workflow for
post-review text.

Supplemental work packages are append-only. They must preserve existing
execution and review evidence and only queue new `WP-S###` packages.

### Recovery

`ExecutionRecoveryFlow` owns persisted interrupted execution state. Retry
preparation must record the selected package set in `execution_run` and leave
execution package state consistent with the retry plan.

Abort and mark-interrupted operations must emit recovery events so Textual and
reports can distinguish user cancellation from provider failure.

The stable recovery summary and retry plan fields are tracked in
`docs/development/provider-readiness-recovery-contracts.md`.

## Refactor Rules

Before removing another `WorkflowEngine` wrapper:

1. Confirm the method is private or has an explicit migration note.
2. Search for direct callers outside `engine.py`.
3. Confirm the owning flow has focused tests for the behavior.
4. Run `uv run python scripts/run_required_smoke_tests.py -q`.
5. Update this document or `docs/development/facade-drift-audit.md` if the
   public boundary changes.

`WorkflowEngine._persist()` has been removed. New event-writing code should call
`engine._persistence_flow().persist()` or accept `WorkflowPersistenceFlow.persist`
as an injected callback.

## Focused Test Guidance

Use focused tests for the touched flow first, then required smoke:

```bash
uv run pytest -q tests/test_workflow_engine.py tests/test_workflow_execution_flow.py tests/test_workflow_review_flow.py tests/test_workflow_post_review_flow.py
uv run python scripts/run_required_smoke_tests.py -q
```
