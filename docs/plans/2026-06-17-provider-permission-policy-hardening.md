# Provider Permission Policy Hardening

Date: 2026-06-17

Branch: `codex/provider-permission-policy-hardening`

## Problem

Trinity already tracks provider invocation intent with `InvocationAccess`:

- `read-only` for deliberation, central synthesis, and review
- `workspace-write` for approved work package execution

However, provider CLI permission flags are currently assembled inside each invoker.
That makes the effective permission model uneven:

- Claude defaults include `--dangerously-skip-permissions`, so Trinity's
  `read-only` intent is not enforced by the Claude CLI.
- Codex mostly maps access to `--sandbox read-only|workspace-write`, but the
  read-only resume path can bypass the normal sandbox/cwd argument path.
- Antigravity uses `--sandbox` for read-only and removes it for workspace-write,
  but there is no shared policy object or common permission failure
  classification.

The product goal is not only to make the UI simple, but to make internal
agent orchestration safe enough to explain: providers should work in the
selected target workspace, with read/review calls constrained differently from
implementation calls.

## Goals

1. Remove dangerous provider bypass defaults from Trinity-generated Claude
   configuration.
2. Introduce a common provider permission policy that maps
   `InvocationAccess` to provider-specific CLI arguments.
3. Make the policy explicit for Claude, Codex, and Antigravity.
4. Normalize permission/sandbox failures into a structured status so execution
   can block/fallback instead of silently treating the result as generic
   failure.
5. Add focused tests for command construction, dangerous argument filtering,
   and permission failure classification.

## Non-Goals

- Full OS sandboxing, chroot, containerization, or filesystem syscall
  interception.
- Guaranteeing that every provider CLI prevents all writes outside target
  workspace. Trinity still needs post-run write auditing as a later layer.
- Solving provider-internal subagent permission models. Trinity can constrain
  the top-level CLI invocation and inspect results, but provider internals
  remain provider-owned.

## Current Permission Model

| Provider | Current read-only behavior | Current workspace-write behavior | Gap |
| :--- | :--- | :--- | :--- |
| Claude | `read-only` in Trinity metadata, but CLI gets inherited extra args including dangerous bypass | Same dangerous bypass | Weakest boundary |
| Codex | `--sandbox read-only --cd <cwd>` except read-only resume path | `--sandbox workspace-write --cd <cwd>` | Resume path policy gap |
| Antigravity | `--sandbox` | no `--sandbox` | No shared policy/failure classifier |

## Proposed Design

Add a provider permission policy layer under `trinity.providers`.

```text
PromptRequest
  -> ProviderPermissionPolicy.build(provider, access, cwd, extra_args)
  -> ProviderPermissionPlan(args, sanitized_extra_args, diagnostics)
  -> Provider-specific invoker assembles final command
```

The policy owns:

- access-to-argv mapping
- dangerous/bypass argument filtering
- duplicate/conflicting permission flag cleanup
- provider-agnostic permission failure classification terms

### Provider Mapping

| Provider | `READ_ONLY` CLI policy | `WORKSPACE_WRITE` CLI policy |
| :--- | :--- | :--- |
| Claude | `--permission-mode plan` plus read-oriented tool allowlist | `--permission-mode acceptEdits` |
| Codex | `--sandbox read-only --cd <cwd>` | `--sandbox workspace-write --cd <cwd>` |
| Antigravity | `--sandbox` | no known safe write flag yet; use target cwd plus follow-up audit |

Claude dangerous bypass flags are removed from default config and filtered from
provider extra args unless a future explicit escape hatch is designed.

Codex `exec resume` currently does not expose `--sandbox`/`--cd` in the checked
CLI help. Trinity should prefer a fresh sandboxed `codex exec` call over an
unsafe read-only resume path until a sandbox-aware resume option is available.

### Failure Classification

Add `permission_required` to `ResponseStatus`.

The invoker base classifier should detect common provider failure text such as:

- permission denied
- not allowed
- sandbox denied
- requires approval
- user denied
- operation not permitted
- permission mode

Execution currently converts non-OK provider messages into failed work package
results. For permission failures, it should return `WorkStatus.BLOCKED` with a
blocker message, allowing fallback attempts and making the UI reason explicit.

## Testing Strategy

Focused tests:

- Claude command construction:
  - read-only adds `--permission-mode plan`
  - workspace-write adds `--permission-mode acceptEdits`
  - `--dangerously-skip-permissions` is not emitted even if old config carries it
  - caller-supplied conflicting `--permission-mode` is replaced by policy mode
- Codex command construction:
  - normal read-only and workspace-write keep sandbox/cwd
  - read-only provider-session continuity does not use `codex exec resume` when
    doing so would drop sandbox/cwd policy
  - conflicting sandbox flags in `extra_args` are not allowed to override policy
- Antigravity command construction:
  - read-only includes `--sandbox`
  - workspace-write omits `--sandbox` but keeps cwd and diagnostics
  - conflicting sandbox args are deduped consistently
- Failure classification:
  - provider stderr/stdout with permission wording returns
    `ResponseStatus.PERMISSION_REQUIRED`
  - execution collection maps `permission_required` to `WorkStatus.BLOCKED`
  - blocked permission attempt participates in fallback attempt chain

Regression tests:

```bash
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_provider_permission_policy.py \
  tests/test_provider_invoker_claude.py \
  tests/test_provider_invoker_codex.py \
  tests/test_provider_invoker_antigravity.py \
  tests/test_execution_protocol.py -q
```

Full suite before PR:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q
```

## Risks

- Claude `--permission-mode plan` in print mode may refuse tool use more often,
  increasing blocked outcomes during planning/review. This is acceptable if the
  UI reports `permission_required` clearly.
- Claude `--permission-mode acceptEdits` may still ask for Bash/tool approval.
  In one-shot execution that can surface as blocked/timeout. Fallback and clear
  classification are required.
- Provider CLI flag support can drift. Tests should isolate Trinity command
  construction, while readiness/bootstrap should surface unsupported flag
  failures as actionable diagnostics.

## Implementation Phases

1. Add common permission policy and tests.
2. Remove Claude dangerous default args from generated config/setup defaults.
3. Wire permission policy into Claude, Codex, and Antigravity invokers.
4. Add `permission_required` response status and execution blocked mapping.
5. Run targeted and full regression tests.
