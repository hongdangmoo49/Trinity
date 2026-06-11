# Central Agent Provider Session Continuity

Date: 2026-06-11

Branch: `feature/central-agent-provider-session-continuity`

Status: implementation in progress

## Goal

Provider-backed central synthesis should keep its own provider-native session
across Trinity workflow resume. If the central agent uses Codex, Claude, or
Antigravity for synthesis, the next synthesis call should be able to continue
that central synthesis conversation instead of always starting a new provider
session.

## Problem

Regular worker agents already persist provider-native session IDs through
`WorkflowSession.provider_sessions`. The central synthesis call used the same
provider invokers, but it did not:

- pass a restored `provider_session_id` into `PromptRequest`;
- expose the synthesis provider's returned `provider_session` metadata;
- merge synthesis provider metadata into `DeliberationResult.metadata`;
- separate central synthesis sessions from normal worker-agent sessions.

Using the worker agent name directly would make a central Codex session and a
worker Codex session collide because provider session keys are based on provider,
agent name, access lane, cwd, and model.

## Design

Central synthesis uses a distinct logical provider-session owner:

```text
central:<provider-agent>
```

Examples:

- Codex-backed central synthesis: `central:codex`
- Claude-backed central synthesis: `central:claude`
- Antigravity-backed central synthesis: `central:antigravity`

The user-facing selected provider agent is still stored as `provider_agent`, but
the provider session mapping uses `provider_session_agent`.

## Runtime Flow

1. `TrinityOrchestrator` selects the synthesis provider.
2. It derives `provider_session_agent = central:<agent>`.
3. It looks up the latest read-only provider session for that logical owner.
4. `ModelBackedSynthesisAgent` sends the synthesis `PromptRequest` with:
   - `agent_name = provider_session_agent`;
   - `provider_session_id = restored central session id`;
   - `continuity_enabled = true` when a session exists.
5. The provider invoker returns normalized `provider_session` and
   `runtime_model` metadata.
6. `DeliberationProtocol` merges that synthesis metadata into the final
   `DeliberationResult.metadata`.
7. `WorkflowEngine` persists it in `WorkflowSession.provider_sessions` and
   `WorkflowSession.runtime_models`.

## Expected Result

After `/resume`, a new orchestrator receives the restored workflow
`provider_sessions`. The central synthesis agent can find the latest
`central:<agent>` read-only session and continue the provider-native
conversation without reusing or overwriting the worker agent's own session.

## Validation

- `ModelBackedSynthesisAgent` passes restored provider session IDs into
  `PromptRequest`.
- `DeliberationProtocol` collects central synthesis provider session metadata.
- `TrinityOrchestrator` restores only `central:<agent>` sessions for central
  synthesis.
- `WorkflowEngine` persists and reloads central provider sessions and runtime
  model metadata.
