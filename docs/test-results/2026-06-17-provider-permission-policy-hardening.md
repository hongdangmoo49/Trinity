# Provider Permission Policy Hardening

Date: 2026-06-17

Branch: `codex/provider-permission-policy-hardening`

## Scope

- Added a common provider permission policy for Claude, Codex, and Antigravity.
- Removed Trinity-generated Claude `--dangerously-skip-permissions` defaults.
- Mapped Claude read-only calls to `--permission-mode plan` with read-oriented
  tools and workspace-write calls to `--permission-mode acceptEdits`.
- Kept Codex calls on sandboxed `exec` paths and avoided unsafe read-only
  `resume` when it would drop sandbox/cwd policy.
- Kept Antigravity read-only calls sandboxed and filtered dangerous bypass args.
- Added `permission_required` provider response status.
- Mapped permission-required execution and review results to blocked outcomes.
- Added command construction, extra-arg filtering, failure classification,
  fallback, and E2E continuation regression tests.

## Validation

```bash
PYTHONPATH=src .venv/bin/python -m py_compile \
  src/trinity/providers/permissions.py \
  src/trinity/providers/invoker.py \
  src/trinity/models.py \
  src/trinity/config.py \
  src/trinity/setup/detector.py \
  src/trinity/workflow/execution.py \
  src/trinity/workflow/review_execution.py \
  src/trinity/deliberation/protocol.py
# passed

PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_provider_permission_policy.py \
  tests/test_provider_invoker_claude.py \
  tests/test_provider_invoker_codex.py \
  tests/test_provider_invoker_antigravity.py -q
# 33 passed

PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_execution_protocol.py \
  tests/test_review_execution_protocol.py \
  tests/test_claude_agent.py \
  tests/test_provider_bootstrap.py \
  tests/test_config.py -q
# 97 passed

PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_provider_permission_policy.py \
  tests/test_provider_invoker_claude.py \
  tests/test_provider_invoker_codex.py \
  tests/test_provider_invoker_antigravity.py \
  tests/test_execution_protocol.py \
  tests/test_review_execution_protocol.py \
  tests/test_deliberation.py \
  tests/test_synthesis_agent.py \
  tests/test_textual_snapshot.py \
  tests/test_textual_app.py \
  tests/test_setup_wizard.py \
  tests/test_provider_bootstrap.py \
  tests/test_config.py -q
# 332 passed

PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_question_answer_target_e2e.py::test_question_answer_continuation_invokes_only_saved_target_agent_model_and_session -q
# 1 passed

PYTHONPATH=src .venv/bin/python -m pytest -q
# 1560 passed, 1 warning
```

## CLI Smoke

Ran the real `trinity ask` CLI entrypoint from a temporary project with fake
`claude`, `codex`, and `agy` executables. The fake providers recorded argv and
stdin, then returned deterministic provider output.

Observed invocation policy:

```json
{
  "claude_permission_mode": "plan",
  "claude_tools": "Read,LS,Grep,Glob",
  "codex_sandbox": "read-only",
  "codex_cd": "/tmp/trinity-permission-cli-*/project",
  "agy_sandbox": true
}
```

The smoke verified the actual CLI path applies read-only policy to all three
providers and does not pass dangerous bypass args.

## Remaining Follow-up

- Add post-run target workspace write audit for all providers.
- Decide whether Claude workspace-write should restrict tools further than
  `acceptEdits`.
- Investigate a future Codex sandbox-aware resume path if the CLI adds
  `--sandbox`/`--cd` support for `exec resume`.
