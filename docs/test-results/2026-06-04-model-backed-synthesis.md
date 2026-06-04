# Model-backed Central Synthesis Implementation Result

- Date: 2026-06-04
- Branch: `codex/model-backed-synthesis`
- Plan: `docs/plans/2026-06-04-model-backed-synthesis.md`

## Completed

1. Synthesis configuration
   - Added `[deliberation]` keys: `synthesis_mode`, `synthesis_agent`,
     `synthesis_model`, `synthesis_timeout_seconds`, `synthesis_max_input_chars`.
   - Defaults: `auto`, empty override, `fast`, `30`, `60000`.
   - `synthesis_mode` accepts only `auto | model | heuristic`.

2. `ModelBackedSynthesisAgent`
   - Uses the existing `ProviderInvoker` one-shot contract.
   - Requests a strict JSON object and extracts the first valid JSON object from output.
   - Validates `summary_for_shared_md`, `total_agents`, `agreement_count`,
     open questions, and blueprint validity.
   - Converts JSON into `OpenQuestion`, `DecisionRecord`, `Blueprint`,
     `StructuredConsensusResult`, and `ConsensusResult`.
   - Normalizes consensus to false when open questions exist or no valid blueprint exists.

3. Fallback behavior
   - Provider timeout/auth/invalid status, JSON extraction failure, and schema validation
     failure fall back through `FallbackSynthesisAgent`.
   - Fallback metadata includes `fallback_used` and `fallback_reason`.

4. Orchestrator wire-up
   - `synthesis_mode="heuristic"` skips provider-backed synthesis.
   - `auto` and `model` choose an active one-shot provider by fixed priority:
     `codex -> claude -> antigravity`.
   - `synthesis_agent` override must point to an enabled active agent and bypasses
     automatic priority.
   - `synthesis_model="fast"` maps to provider-specific synthesis defaults:
     `codex:gpt-5.4-mini`, `claude-code:sonnet`, `antigravity-cli:default`.
   - Readiness degraded mode refreshes the synthesis provider after narrowing agents.

5. Artifacts and shared.md
   - Writes `.trinity/synthesis/round-XX/synthesis.raw.txt` and `synthesis.json`.
   - Writes `synthesis.diagnostics.txt` when diagnostics exist.
   - Adds source, provider, model, fallback metadata, and fallback reason to
     `Round N Synthesis`.

6. Status/config visibility
   - `trinity status` and TUI `/status` show synthesis mode/provider/model/fallback state.
   - `trinity config` can display synthesis settings.

7. Template update
   - Added synthesis defaults to `templates/trinity.config.example`.
   - Documented automatic provider priority and provider-specific `fast` models.

## Model Default Rationale

- Codex uses `gpt-5.4-mini`, matching Trinity's known Codex model context and the
  existing project template.
- Claude Code uses `sonnet`, the documented fast/intelligent alias accepted by
  Claude Code `--model`.
- Antigravity uses `default` because official docs expose persistent reasoning
  model selection through `/model`, while a stable non-interactive CLI model slug
  contract is not documented. For fast Antigravity synthesis, set the Antigravity
  CLI default to Gemini 3 Flash in `/model`.

## Validation

Targeted tests:

```text
uv run pytest tests/test_synthesis_agent.py tests/test_config.py tests/test_shared_context.py tests/test_orchestrator.py -q
97 passed in 0.49s
```

Lint:

```text
uv run --with ruff ruff check src/trinity/config.py src/trinity/deliberation/synthesis.py src/trinity/deliberation/__init__.py src/trinity/deliberation/protocol.py src/trinity/context/shared.py src/trinity/orchestrator.py src/trinity/cli.py src/trinity/tui/session.py src/trinity/providers/__init__.py tests/test_synthesis_agent.py tests/test_config.py tests/test_shared_context.py tests/test_orchestrator.py
All checks passed!
```

Full test suite:

```text
uv run pytest -q
976 passed, 1 warning in 21.88s
```

The warning is the existing `tests/test_error_handling.py::TestCrashRecording::test_history_all_agents`
`AsyncMockMixin._execute_mock_call` unawaited coroutine warning, not a failure from this change.

## Remaining Verification

- Run a real provider CLI smoke test before release because model-backed synthesis depends on local auth state.
- Antigravity has no machine-readable output contract, so JSON compliance depends on model behavior;
  heuristic fallback remains the safety path.
