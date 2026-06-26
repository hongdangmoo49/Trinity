# Provider Readiness And Recovery Contracts

This document records the current provider readiness, provider error retry, and
execution recovery contracts. Use it before changing provider startup checks,
degraded-mode behavior, retry prompts, or interrupted execution recovery.

## Scope

Authoritative implementation modules:

- `src/trinity/providers/readiness.py`
  - interactive pane readiness classification
  - one-shot CLI preflight
  - provider state, reason, action hint, and diagnostics shape
- `src/trinity/orchestrator_readiness.py`
  - orchestration-level readiness runtime
  - degraded-mode agent rebinding
  - provider readiness events and failure result formatting
- `src/trinity/workflow/provider_error_gate.py`
  - pre-synthesis provider failure gate planning
  - retry prompt and retry merge context
- `src/trinity/workflow/provider_error_gate_flow.py`
  - stateful retry, continue, and stop handling for provider failures
- `src/trinity/workflow/recovery_flow.py`
  - interrupted execution detection
  - retry plan creation
  - retry, mark-interrupted, and abort state transitions

## Provider State Contract

`ProviderState` is the public classification vocabulary for readiness and
preflight results. UI, reports, lifecycle guards, and tests may depend on these
values:

- `ready`
- `auth_required`
- `model_loading`
- `workspace_trust_required`
- `cli_banner_only`
- `prompt_not_sent`
- `process_dead`
- `cwd_inaccessible`
- `cli_not_found`
- `cli_probe_failed`
- `model_unavailable`
- `permission_plan_invalid`
- `unknown_not_ready`

Do not rename or remove a state without a migration note and focused tests for
Textual status projection, provider panels, and reports.

Every `ReadinessResult` must include:

- `agent_name`
- `provider`
- `ready`
- `state`
- `reason`
- `action_hint`
- optional `excerpt`

Every `OneShotPreflightResult` must also preserve diagnostics used by provider
inspector and status output:

- `cwd`
- `cli_command`
- `resolved_executable`
- `probe_command`
- `probe_returncode`
- `model`
- `model_source`
- `model_source_reason`
- `discovered_models`
- `access`
- `permission_args`
- `permission_extra_args`
- `permission_diagnostics`

## Interactive Readiness

`ProviderReadinessGate` checks interactive agents with panes. Print-mode agents
without panes are considered ready because they do not require pane prompt
gating.

Interactive pane classification must follow this priority:

1. Ready prompt detection.
2. Dead process detection.
3. Workspace trust prompt detection.
4. Authentication prompt detection.
5. Model loading detection.
6. CLI banner-only detection.
7. Unknown not-ready fallback.

`wait_until_ready()` may keep polling transient states, but it must return
immediately for terminal not-ready states:

- `auth_required`
- `workspace_trust_required`
- `process_dead`

## One-Shot Preflight

`OneShotProviderPreflight.check()` validates a one-shot agent before dispatch.
It must fail before provider invocation when any of these prerequisites fail:

1. Launch cwd exists and is accessible.
2. CLI command is non-empty and resolvable.
3. CLI probe succeeds.
4. Permission plan is valid for the requested `InvocationAccess`.
5. Requested discoverable model is available.

One-shot checks must include the requested access level. Execution/review
dispatch that may write files must call preflight with
`InvocationAccess.WORKSPACE_WRITE`.

## Orchestrator Runtime Contract

`OrchestratorReadinessRuntime` returns a `ReadinessRuntimeOutcome`. It does not
mutate the live orchestrator directly.

`OrchestratorReadinessBinder` is the only component that applies readiness
outcomes to the orchestrator. When degraded mode continues with a subset of
ready agents, the binder must rebind:

- `orchestrator.agents`
- deliberation protocol agents and synthesis agent
- execution protocol agents
- review protocol agents
- context monitor agents
- session rotator agents
- health checker agents

Readiness checks must emit one `PROVIDER_READINESS` event per checked provider.
If strict readiness fails before deliberation starts, the runtime must return a
failure `DeliberationResult` and emit `DELIBERATION_DONE` through the binder.

## Strict And Degraded Modes

`provider_readiness_mode = strict` means any not-ready provider blocks
deliberation startup or one-shot dispatch.

`provider_readiness_mode = degraded` means Trinity may continue only when at
least one provider is ready. All runtime components must be rebound to exactly
that ready-provider subset before additional workflow traffic is sent.

Degraded mode must not silently continue with zero ready providers.

## Provider Error Gate

The provider error gate is distinct from startup readiness. It handles provider
failures returned during deliberation before central synthesis.

The gate opens only for retryable provider failures and creates the fixed
question id `q-provider-error-retry`.

Supported user choices:

- `retry`
  - keep successful provider opinions in merge context
  - target only failed agents
  - return a deliberation action
- `continue`
  - allowed only when preserved successful opinions form usable consensus
  - clear the gate
  - mark the stored deliberation result
- `stop`
  - clear the gate
  - transition workflow to `FAILED`

The retry context must preserve:

- `successful_opinions`
- `retry_agents`
- `original_prompt`
- `source_question_id`

## Execution Recovery

Execution recovery is owned by `ExecutionRecoveryFlow`.

`detect_interrupted_execution()` must only mark recovery when:

- no worker is running
- the workflow is in `EXECUTING`
- the execution run is `running` or stale package state implies interruption

When interruption is detected, the flow must:

- set `execution_run.state = interrupted`
- record `interrupted_reason`
- record `interrupted_at`
- capture currently running package ids
- emit `execution_interrupted_detected`

`execution_recovery_summary()` is user-facing and report-facing. It must keep
these fields stable:

- `run_id`
- `state`
- `target_workspace`
- `started_at`
- `heartbeat_at`
- `interrupted_reason`
- `running_packages`
- `done_packages`
- `retry_candidates`
- `last_event_at`
- `last_event`

## Retry Plan Contract

`build_execution_retry_plan()` is non-destructive. It may select failed,
blocked, or interrupted packages but must not mutate package state.

Supported selectors:

- `all`
- `failed`
- `blocked`
- `interrupted`
- `custom`

`prepare_execution_retry()` is destructive by design. It must:

- detect stale running packages before planning
- set selected packages back to `PENDING`
- clear selected package `current_executor`
- clear selected repair-block markers
- mark unselected stale running packages as `BLOCKED`
- set `execution_run.state = retry_requested`
- set `retry_selector`
- set `retry_packages`
- emit `work_package_retry_requested` and `execution_recovery_action`
- transition the workflow to `BLUEPRINT_READY`

The previous execution results must be preserved. Retry is append-only with
respect to evidence.

## Mark Or Abort Contract

`mark_interrupted_execution()` turns running packages into `BLOCKED`, persists
`execution_recovery_action` with `mark_interrupted`, and moves the workflow to
`NEEDS_USER_DECISION`.

`abort_interrupted_execution()` marks the execution run as `aborted`, turns
running retry candidates into `BLOCKED`, persists `execution_recovery_action`
with `abort_execution`, and moves the workflow to `NEEDS_USER_DECISION`.

Neither operation should delete execution results, review results, or workflow
events.

## Focused Test Guidance

Use these tests for readiness/recovery changes before required smoke:

```bash
uv run pytest -q \
  tests/test_provider_readiness.py \
  tests/test_orchestrator_readiness.py \
  tests/test_provider_error_gate_flow.py \
  tests/test_workflow_engine.py::test_detect_interrupted_execution_when_running_without_worker \
  tests/test_workflow_engine.py::test_retry_interrupted_packages_excludes_done_packages \
  tests/test_workflow_engine.py::test_build_execution_retry_plan_selects_failed_blocked_and_interrupted \
  tests/test_workflow_engine.py::test_prepare_execution_retry_detects_stale_running_before_retry \
  tests/test_workflow_engine.py::test_prepare_execution_retry_keeps_unselected_failed_packages_out_of_dispatch \
  tests/test_workflow_engine.py::test_prepare_execution_retry_clears_selected_repair_block_marker
uv run python scripts/run_required_smoke_tests.py -q
```
