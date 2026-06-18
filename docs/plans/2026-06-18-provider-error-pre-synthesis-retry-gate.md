# Provider Error Pre-Synthesis Retry Gate Hardening

Date: 2026-06-18

Branch: `codex/task-b-provider-retry-gate`

Status: implementation plan

## Problem

The current provider error retry gate is opened only after the deliberation
protocol has already synthesized the successful provider opinions. The workflow
engine does pause before applying the blueprint, but the synthesis has already
been written to the canonical `Round N Synthesis` shared context section and
may be projected by Nexus as if it were authoritative.

Retry also starts a new targeted deliberation for failed providers only. That
means retry synthesis can be based solely on the retried opinions instead of
the union of prior successful opinions and retry output.

## Goals

1. Prevent partial synthesis from becoming authoritative before the user chooses
   retry, continue, or stop.
2. Preserve the existing UX options when a usable partial synthesis exists:
   retry failed providers, continue without failed providers, or stop.
3. When retry is selected, synthesize from the merged opinion set:
   previous successful opinions plus successful retry opinions.
4. If retry still fails for any provider, open the gate again using the merged
   successes collected so far.
5. Keep the scope limited to deliberation provider failure gate behavior.

## Non-Goals

- Changing provider readiness preflight policy.
- Changing work-package execution retry/recovery behavior.
- Reworking general structured consensus or blueprint decomposition.
- Adding new user-facing provider configuration.

## Chosen Design: Two-Phase Retry Merge

A true protocol-level pause before synthesis would require a separate runtime
path that can later synthesize stored opinions without asking providers again.
The current controller/orchestrator boundary only knows how to start a provider
deliberation run, so that approach would be larger and would weaken the
existing "continue without failed providers" option.

Instead, this change treats initial synthesis with retryable provider failures
as a provisional preview:

1. The protocol collects provider opinions and identifies retryable failures.
2. It may synthesize successful opinions so the UI can offer "continue without
   failed providers" only when there is a usable result.
3. When retryable failures exist, the protocol does not write canonical
   `Round N Synthesis` or `Agreed Conclusion` sections. The result metadata is
   marked as `provider_error_gate_status=provisional`.
4. The workflow engine stores the provisional result and the successful opinion
   map inside `session.provider_error_gate`.
5. If the user chooses continue, the stored provisional result is explicitly
   applied and marked gate-bypassed.
6. If the user chooses retry, only failed providers are invoked, but the retry
   protocol receives a merge context containing prior successful opinions.
7. Retry synthesis uses `{previous_successes} + {retry_successes}`. Retry
   failures replace only the failed-provider entries and can reopen the gate.

This prevents stale partial synthesis from becoming authoritative while keeping
the UX responsive and preserving current workflow state semantics.

## Data Contract

`DeliberationResult.metadata` gains provider-gate fields:

- `provider_error_gate_status`: `""`, `"provisional"`, or `"merged_retry"`.
- `provider_successful_opinions`: successful opinion text keyed by agent.
- `provider_retry_merge`: metadata describing merge source agents and retry
  agents when a retry run merged prior successes.

`WorkflowInputAction` gains a provider-error retry merge context passed through
the Textual controller into the orchestrator/protocol.

`WorkflowSession.provider_error_gate` stores:

- `result`: serialized provisional result.
- `successful_opinions`: successful opinions that must be retained across retry.
- `failures` and `failed_agents`: current retryable failures.
- `state`: `waiting` or `retry_requested`.

## Protocol Behavior

Normal run with no retryable failures:

- unchanged.
- write `Round N Synthesis`.
- return consensus/structured consensus normally.

Initial run with retryable failures:

- collect and validate all responses.
- synthesize usable opinions for preview/continue eligibility.
- do not write `Round N Synthesis`.
- do not write `Agreed Conclusion`.
- return metadata with `provider_error_gate_status=provisional` and
  `provider_successful_opinions`.

Retry run:

- collect responses only from failed providers.
- merge prior successful opinions with retry successful opinions before
  synthesis.
- keep retry failures in `provider_failures`.
- if retry failures remain, do not write canonical synthesis and let the
  workflow gate reopen with the expanded successful opinion map.
- if no retry failures remain, write canonical synthesis and return normally.

## Workflow Behavior

`mark_deliberation_result()` continues to own the gate decision:

- Retryable failures open the gate before any blueprint/work-package state is
  applied.
- Continue applies the stored provisional result with
  `provider_error_gate_bypassed=True`.
- Stop clears the gate and marks the workflow failed.
- Retry returns `WorkflowInputAction.should_deliberate=True` for failed agents
  and includes the merge context.

When a retry result returns, `mark_deliberation_result()` treats it like any
other deliberation result. If retry failures remain, the gate opens again; if
not, the merged synthesis is applied.

## UI Behavior

The existing Nexus provider-error buttons remain:

- Retry failed
- Continue without
- Stop

Because canonical shared synthesis is no longer written while the gate is open,
the central panel should show the question/action state rather than a stale
`Round N Synthesis` section.

## Tests

Focused regression coverage:

- Protocol returns provider failure metadata and successful opinions.
- Protocol does not write `Round N Synthesis` while retryable failures are
  pending.
- Retry protocol merges prior successful opinions with retry successes before
  synthesis.
- Workflow retry action carries failed-agent targeting plus merge context.
- Workflow continue still applies the stored provisional result.
- Existing Nexus provider-error action buttons still answer the gate question.

Run focused tests:

```bash
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_protocol.py \
  tests/test_workflow_engine.py \
  tests/test_textual_workflow_controller.py \
  tests/test_textual_app.py
```
