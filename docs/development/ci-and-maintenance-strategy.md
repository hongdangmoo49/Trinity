# CI and Maintenance Strategy

This document records the maintenance plan after the large Nexus, workflow, UI,
and performance iteration. It is intentionally practical: use it to decide what
Codex runs locally, what GitHub Actions must block, what needs periodic cleanup,
and what the next release train should optimize.

## Current Evidence

- Baseline branch inspected: `main`
- Package version inspected: `1.0.330`
- Merged PR range reviewed: #90 through #426
- PRs reviewed in that range: 336 merged PRs
- Required CI workflows inspected:
  - `.github/workflows/cross-platform-smoke.yml`
  - `.github/workflows/publish-pypi.yml`
- Required smoke test list:
  - `.github/required-smoke-tests.txt`
- Local/CI smoke runner:
  - `scripts/run_required_smoke_tests.py`

## Recent PR Bundles

### #90-#96: Test Harness and Facade Baseline

- Added the fake provider smoke harness.
- Split early Textual presenter logic.
- Split WorkflowEngine error recovery, execution, and review flows.
- Split Orchestrator readiness runtime.
- Clarified facade boundaries before the larger iteration continued.

### #97-#108: Nexus Projection and Performance Budgets

- Limited workflow event projection tails.
- Added Execution Matrix row-level updates.
- Avoided repeated Nexus Inspector refreshes.
- Made Nexus cache keys and raw artifacts lighter.
- Added snapshot performance budget coverage.
- Removed AsyncMock warning noise.

### #109-#160: Execution UX, Retry, Review, and Report Feedback

- Added no-peer review explanations for one-provider or two-provider setups.
- Added Execution Matrix log toggles, retry actions, parallel group labels,
  review labels, blocked-row actions, and lane metadata.
- Surfaced output contract, routing metadata, profile metadata, and quality
  signals across Provider UI and reports.
- Added retry modal localization and second-review affordances.
- Added bounded log modal rendering and search result counts.

### #161-#292: Korean UX and Status Vocabulary Stabilization

- Localized workflow, questions, decisions, packages, subtasks, history, review,
  improve, answer, report, save, target, rounds, agent, resume, execute, context,
  memory, and artifact command surfaces.
- Standardized Korean terminology for provider, workspace, work package,
  no-peer review, recovery, output contract, profile revision, action context,
  risk, severity, state, and placeholder labels.
- Improved waiting/succeeded status bucketing and progress summaries.
- Improved workspace branch fallback and `.git` file branch detection.

### #293-#391: Nexus/Textual Render Cost Reduction

- Reduced repeated slicing, filtering, lookup, and field updates in execution
  logs, Execution Matrix, ProviderPanel, CentralAgentView, QuestionPanel,
  PromptComposer, ReportScreen, Start, Settings, ModelSettings, and Workspace
  Picker.
- Added identity caches, render-key caches, widget caches, status-key
  normalization, and cache rebind safeguards.
- The goal of this bundle was not new UX; it was preventing Nexus from slowing
  down when workflow snapshots and activity logs update frequently.

### #392-#409: Workflow Flow Decomposition

- Split provider error gate, execution, review, post-review, lifecycle,
  workspace, quality, targeting, collection, input routing, question handling,
  provider observations, central interaction, and ledger sync into dedicated
  modules.
- Moved helper logic into flow modules so `WorkflowEngine` can remain a facade
  over durable workflow behavior.

### #410-#426: Textual Presenter and Wrapper Removal

- Continued extracting pure presenter/parser functions from Textual app logic.
- Removed obsolete private wrappers from Textual and workflow facades.
- Reused provider error gate flow helpers directly.
- Thinned workflow execution/recovery facades after the flow modules became the
  authoritative implementation.

## Main Structure

### CLI and Setup

- `src/trinity/cli.py` owns command dispatch and user-facing CLI entry points.
- `src/trinity/setup/` owns detection and setup wizard behavior.
- `src/trinity/updater.py` owns PyPI update checks and update prompts.

### Providers and Agents

- `src/trinity/agents/` owns provider-specific agent wrappers.
- `src/trinity/providers/` owns CLI invocation, model discovery, bootstrap,
  permission policy, and readiness checks.
- `src/trinity/agent_profiles.py` and `src/trinity/routing/` own richer agent
  profiles, output contracts, routing, and quality policy.

### Workflow Runtime

- `src/trinity/orchestrator.py` should stay thin and coordinate high-level
  orchestration.
- `src/trinity/orchestrator_readiness.py` owns readiness runtime decisions.
- `src/trinity/workflow/engine.py` should stay a facade over the dedicated flow
  modules.
- `src/trinity/workflow/*_flow.py`, `provider_error_gate*.py`,
  `ledger_sync.py`, and `provider_observations.py` own durable workflow behavior.

### Textual/Nexus UI

- `src/trinity/textual_app/app.py` should stay thin around screen mounting,
  runtime wiring, and command routing.
- `src/trinity/textual_app/presenters.py` and `command_parsers.py` should own
  pure formatting and command parsing.
- `src/trinity/textual_app/screens/` and `widgets/` should own UI state
  application, caching, and bounded rendering.

### Context, Deliberation, and Reports

- `src/trinity/context/` owns context budget, compression, commands, memory, and
  shared context.
- `src/trinity/deliberation/` owns consensus and synthesis protocol behavior.
- `src/trinity/tui/` remains the non-Textual terminal surface and should not
  regain Nexus-specific responsibilities.

### Tests

- `tests/harness/` owns reusable fake/replay/performance harnesses.
- `tests/test_fake_provider_harness.py` is the account-free provider contract
  gate.
- Workflow flow tests should stay close to their modules:
  - `tests/test_workflow_execution_flow.py`
  - `tests/test_workflow_review_flow.py`
  - `tests/test_workflow_post_review_flow.py`
  - `tests/test_provider_error_gate_flow.py`

## Test Strategy

### Codex Local Loop

Run the smallest focused set that proves the touched contract.

| Change area | Local default |
| --- | --- |
| CLI, updater, packaging | `uv run pytest -q tests/test_cli.py tests/test_updater.py` |
| Provider discovery/readiness/invocation | `uv run pytest -q tests/test_provider_model_discovery.py tests/test_provider_readiness.py tests/test_fake_provider_harness.py` |
| Provider error/retry/recovery | `uv run pytest -q tests/test_provider_error_gate_flow.py tests/test_execution_retry_modal.py` |
| Workflow execution/review/post-review | `uv run pytest -q tests/test_workflow_engine.py tests/test_workflow_execution_flow.py tests/test_workflow_review_flow.py tests/test_workflow_post_review_flow.py` |
| Textual presenter/parser/UI cache | `uv run pytest -q tests/test_textual_smoke.py tests/test_textual_runtime.py tests/test_textual_workflow_controller.py` |
| Nexus execution/log performance | Run the touched cache test plus `uv run pytest -q tests/test_performance_harness.py` when a performance budget is involved. |
| Fake provider harness | `uv run pytest -q tests/test_fake_provider_harness.py` |
| Broad facade or shared model changes | `uv run python scripts/run_required_smoke_tests.py -q` |

Do not run the full suite after every small edit. Run the full suite when a
change crosses module boundaries or before release/version bumps.

### PR Required CI

Pull requests should run the required smoke set only:

```bash
uv run python scripts/run_required_smoke_tests.py -q
```

The required set is intentionally broader than the old smoke list because the
recent iteration moved critical behavior into workflow/provider/Textual flow
modules. It now covers:

- CLI and update prompt basics
- platform process/log tail behavior
- provider bootstrap/readiness/model discovery/fake harness
- provider error gate and retry UI
- orchestrator readiness
- workflow engine execution/review/post-review flows
- Textual runtime and workflow controller smoke
- terminal rendering smoke

### Main and Publish CI

`main` push and PyPI publish preflight should run the same required smoke set.
Publishing also builds the wheel and verifies the installed `trinity` console
script with:

- `trinity --version`
- `trinity init --non-interactive`
- `trinity doctor`
- `trinity bootstrap --check-only --agents claude`

### Full Validation

Use full validation for release candidates, large refactors, or manual
confidence checks:

```bash
uv run pytest -q
```

If GitHub Actions cost becomes acceptable, add a scheduled nightly workflow for
the full suite. Do not make the full suite a required PR gate until the runtime
cost is measured and accepted.

## Cleanup Candidates

### Completed Plan Document Volume

`docs/plans/` now contains many one-PR implementation plans. Before deleting
anything, create a dated index that maps completed plans to the PR bundle above.
After the index exists, old one-PR plans can be archived by date.

### Facade Drift

Keep auditing these files for private wrappers that only forward to a flow:

- `src/trinity/workflow/engine.py`
- `src/trinity/orchestrator.py`
- `src/trinity/textual_app/app.py`

Wrapper removal is safe only when focused flow tests and required smoke tests
cover the public behavior.

### Legacy Runtime Surface

Audit `src/trinity/legacy/`, `src/trinity/tmux/`, and `src/trinity/tui/` before
removal. These may still be compatibility surfaces, so the first step is usage
mapping, not deletion.

Current audit: `docs/development/legacy-runtime-surface-audit.md`.

### Localization Duplication

The Korean UX iteration stabilized labels quickly across many surfaces. A later
cleanup can consolidate repeated status/term mappings into shared presenter
helpers, but only after verifying that Textual, report export, and local command
outputs still need identical wording.

### Cache Key Sprawl

The performance pass added many targeted cache keys. Keep them local while the
UI is still changing. Consolidate only where two widgets share the same snapshot
identity contract and the tests prove the contract.

## Next Release Goals

### Patch Train

- Keep patch releases for isolated bug fixes, smoke list adjustments, and
  low-risk wrapper removals.
- Require focused local tests plus `scripts/run_required_smoke_tests.py`.

### Next Minor

- Ship the CI/test strategy as the default engineering workflow.
- Add and maintain a completed-plan index for `docs/plans/`.
- Continue facade drift audits after each flow contract is documented.
- Maintain the fake-provider E2E path that exercises CLI init, provider
  readiness, workflow execution, retry decision, and report output without real
  accounts.

### Next Major

- Treat `AgentProfile`, provider readiness, workflow recovery, and Nexus
  execution review state as public contracts.
- Stabilize config migration semantics before changing defaults.
- Only promote a major version after the full suite and fake-provider E2E pass
  on all supported platforms.

## Operating Rule

For ordinary Codex-driven PRs:

1. Run focused tests for the touched module.
2. Run `uv run python scripts/run_required_smoke_tests.py -q` before pushing
   when the change touches shared CLI/provider/workflow/Textual behavior.
3. Let PR CI prove cross-platform required smoke.
4. Run `uv run pytest -q` for releases, broad refactors, and uncertainty.
