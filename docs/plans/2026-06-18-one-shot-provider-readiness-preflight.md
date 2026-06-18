# One-Shot Provider Readiness Preflight

Date: 2026-06-18
Status: implementation started
Scope owner: one-shot provider preflight/readiness only

## Problem

One-shot provider calls currently discover failures only when the provider turn is
already underway. That makes missing CLIs, inaccessible launch directories,
unsupported configured models, and permission-policy rewrites appear as generic
provider failures. Interactive mode has pane readiness classification, but
one-shot mode needs a lightweight runtime preflight that validates the concrete
request shape before first provider use.

## Goals

- Validate each configured one-shot provider before it is used.
- Distinguish a missing CLI from a provider runtime failure.
- Validate launch cwd/target workspace accessibility before subprocess launch.
- Validate the configured model when the provider exposes discoverable models.
- Surface permission-policy plans and sanitization diagnostics where applicable.
- Preserve existing setup/model discovery behavior and cache semantics.
- Improve fallback diagnostics when model discovery uses static choices.

## Non-Goals

- No version bump.
- No change to interactive tmux pane readiness behavior.
- No provider auth handshake or expensive model call during preflight.
- No broad workflow or execution-policy redesign.

## Design

Add a one-shot preflight helper in `trinity.providers.readiness` beside the
existing interactive readiness gate. The helper accepts prepared `AgentWrapper`
instances after launch context wiring, because that is where the actual cwd,
env overrides, selected model, extra args, and provider session metadata are
available.

For each print-mode agent the preflight will:

1. Validate `cwd` exists, is a directory, and can be listed.
2. Resolve the configured CLI command using the merged provider environment.
3. Execute a cheap provider-specific probe:
   - Claude Code: `claude --version`
   - Codex: `codex --version`
   - Antigravity: `agy --version`
4. Discover model choices with the existing `discover_provider_models` path for
   discoverable providers. If discovery returns only static fallback choices,
   record that source and do not reject unknown custom model aliases.
5. When live or bundled discovery returns model names, reject an explicit
   configured model that is not present. `default` remains accepted.
6. Build the provider permission plan for the requested access level and return
   its args plus sanitization diagnostics for UI/logging.

The preflight result subclasses `ReadinessResult` so existing readiness
formatting can be reused while the runtime-specific details remain available:

- cwd and resolved executable
- probe command and return code
- model source, source reason, and discovered models
- invocation access and permission-plan diagnostics

## Orchestrator Integration

During `_ensure_initialized`, create the preflight helper after one-shot agents
and launch contexts are prepared, but do not execute CLI probes there. This
keeps status/component initialization from requiring installed provider CLIs.
Run the preflight immediately before one-shot provider dispatch: deliberation
uses read-only access, execution uses workspace-write access, and review uses
read-only access. In strict readiness mode, fail before dispatch if any provider
is not ready. In degraded mode, log and retain the results while continuing with
ready agents when possible. Interactive mode continues to use
`ProviderReadinessGate` for panes.

The orchestrator stores one-shot preflight results separately and mirrors them
into readiness status after a preflight run so callers can inspect current
readiness without confusing this with pane classification.

## Test Plan

- Unit-test cwd failure, missing CLI failure, probe failure, model rejection
  when live discovery is available, static fallback acceptance, and permission
  diagnostics.
- Unit-test orchestrator strict/degraded behavior for one-shot preflight.
- Keep existing model discovery behavior intact, with added assertions for
  fallback source reasons.
