# CI and Maintenance Strategy

This document records the maintenance plan after the large Nexus, workflow, UI,
and performance iteration. It is intentionally practical: use it to decide what
Codex runs locally, what GitHub Actions must block, what needs periodic cleanup,
and what the next release train should optimize.

## Current Evidence

- Baseline branch inspected: `main`
- Package version inspected: `1.0.444`
- Merged PR range reviewed: #90 through #540
- Baseline iteration reviewed: #90 through #426
- Maintenance refresh reviewed: #427 through #540
- Latest refresh reviewed: #487 through #540
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

### #427-#444: Maintenance Contracts, Archive Closure, and Fake E2E

- Added the CI and maintenance strategy, completed-plan index, and focused
  contract documents for Textual presenters, fake providers, render cache,
  workflow flow boundaries, provider readiness/recovery, and Nexus
  execution/review state.
- Added fake-provider workflow E2E coverage and included it in the required
  smoke list so account-free provider behavior is part of the PR gate.
- Audited facade drift and legacy runtime surfaces before deleting more wrapper
  code or compatibility paths.
- Removed the remaining direct private helper delegates from
  `WorkflowEngine` after the flow contracts existed.
- Archived completed plan bundles for Textual presenter work, Korean UX,
  render cache work, UI label/status stabilization, execution/review feedback,
  and fake-provider baseline work.

### #445-#447: Maintenance Refresh and Workflow Facade Cleanup

- Refreshed this maintenance strategy from the first completed-plan archive
  pass.
- Removed the remaining central-flow private delegates from `WorkflowEngine`
  after the central flow contract existed.
- Continued reducing `WorkflowEngine` wrapper drift while keeping public engine
  methods stable.

### #448-#460: Textual Local Command State and Parser Extraction

- Split Textual local command state and local command persistence helpers into
  `textual_app/local_commands.py`.
- Extracted parsers for rounds, agent, caveman, answer, target, resume,
  report, artifact, memory, and execute commands into
  `textual_app/command_parsers.py`.
- Added the Textual command helper tests to the required smoke gate so parser
  and local command regressions fail in PR CI.

### #461-#468: Textual Command Outcome Helper Reuse

- Split review, improve, and execute command handling helpers.
- Reused common workflow outcome message handling for resume, answer, review,
  and Nexus execute paths.
- Reduced duplicated apply-and-present logic across Nexus and Execution Matrix
  command entry points.

### #469-#481: Textual Slash Command Handler and Router Extraction

- Split workflow, questions, decisions, packages, subtasks, history, help,
  save, status, model, and quit command handlers from the main slash command
  dispatcher.
- Added `textual_app/slash_command_router.py` so command-id-to-handler mapping
  is explicit and unit-tested.
- Split syntax-error and unknown-command result handling out of the dispatcher.

### #482-#486: Workflow Result, Readiness, and Target Workspace Helpers

- Split structured and consensus deliberation result application helpers in
  `WorkflowEngine`.
- Split orchestrator readiness outcome application and event emitter helpers.
- Added `textual_app/target_workspace.py` for `/target` path normalization and
  control-repository detection.
- Raised the package version from `1.0.384` to `1.0.389` across these focused
  patch PRs.

### #487-#492: Textual Command Helper Continuation

- Refreshed the maintenance strategy after the first cleanup pass.
- Split safe-start target handling and resume, answer, review, and improve
  command result helpers out of `textual_app/app.py`.
- Kept command parsing and result presentation covered by the Textual command
  helper tests in the required smoke set.

### #493-#517: Workflow Facade Wrapper Cleanup

- Removed obsolete `WorkflowEngine` wrappers for review flow, result
  collection, post-review, work package lookup, execution run, review repair
  metadata, unused result, execution support, quality, provider observation,
  lifecycle/question, central prompt, ledger parsing, targeting, and persist
  helpers.
- Split deliberation result, persistence, execution intent, decomposition
  agent, and direct persistence calls into flow-level modules.
- Updated the workflow flow contract after the wrapper removal pass so future
  cleanup can keep `WorkflowEngine` facade boundaries explicit.

### #518-#533: Textual Route, Workspace, and Review Repair Helpers

- Split local command presentation, execution recovery presentation, review
  repair presentation, route snapshot application, execution route switching,
  report route preparation, and snapshot source handling out of the main
  Textual app.
- Split launch cwd, target workspace preparation, target cancel/confirm modal,
  workspace picker factory, workspace candidate sync, target workspace apply,
  and execution state helpers.
- Split review repair metadata helper logic after the workflow wrapper cleanup.

### #534-#540: Post-Review Helpers, Render Window, Smoke Runner, and Archive

- Split post-review item selection, owner assignment, supplemental
  WorkPackage construction, and supplemental execution run payload construction
  into focused helper modules.
- Limited Nexus workflow event rendering to a smaller UI window while keeping
  the persistence tail available for recovery context.
- Added required smoke runner manifest validation, duplicate detection, and
  `--list` output for local and CI inspection.
- Archived the completed post-review maintenance plan bundle and updated the
  completed-plan index.
- Raised the package version from `1.0.389` to `1.0.443` across these focused
  patch PRs.

This refresh moved the project further from "large batch of one-PR plans" to a
smaller set of durable maintenance documents and focused archive bundles. Root
`docs/plans/` still contains older architecture, migration, and 2026-06-27
mechanical refactor plans; archive only the groups that have a current contract
document, merged PR evidence, and focused test coverage.

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
- `src/trinity/textual_app/local_commands.py`,
  `slash_command_router.py`, and `target_workspace.py` own local command state,
  slash dispatch metadata, and target workspace path helpers.
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
- `tests/test_fake_provider_e2e.py` exercises the fake-provider workflow path
  across init/config, provider readiness, retry decisions, workflow execution,
  and report output.
- Workflow flow tests should stay close to their modules:
  - `tests/test_workflow_execution_flow.py`
  - `tests/test_workflow_review_flow.py`
  - `tests/test_workflow_post_review_flow.py`
  - `tests/test_provider_error_gate_flow.py`
- Textual helper tests should stay close to their extracted helpers:
  - `tests/test_textual_answer_commands.py`
  - `tests/test_textual_command_parsers.py`
  - `tests/test_textual_improve_commands.py`
  - `tests/test_textual_local_commands.py`
  - `tests/test_textual_resume_commands.py`
  - `tests/test_textual_review_commands.py`
  - `tests/test_textual_slash_command_router.py`
  - `tests/test_textual_target_workspace.py`

### Maintenance Documents

These documents are the current durable references for follow-up cleanup:

- `docs/development/textual-presenter-parser-contract.md`
- `docs/development/fake-provider-test-environment.md`
- `docs/development/facade-drift-audit.md`
- `docs/development/legacy-runtime-surface-audit.md`
- `docs/development/korean-ui-glossary.md`
- `docs/development/nexus-render-cache-guidelines.md`
- `docs/development/workflow-flow-contracts.md`
- `docs/development/provider-readiness-recovery-contracts.md`
- `docs/development/nexus-execution-review-state-contracts.md`

## Test Strategy

### Codex Local Loop

Run the smallest focused set that proves the touched contract.

| Change area | Local default |
| --- | --- |
| CLI, updater, packaging | `uv run pytest -q tests/test_cli.py tests/test_updater.py` |
| Provider discovery/readiness/invocation | `uv run pytest -q tests/test_provider_model_discovery.py tests/test_provider_readiness.py tests/test_fake_provider_harness.py` |
| Provider error/retry/recovery | `uv run pytest -q tests/test_provider_error_gate_flow.py tests/test_execution_retry_modal.py` |
| Workflow execution/review/post-review | `uv run pytest -q tests/test_workflow_engine.py tests/test_workflow_execution_flow.py tests/test_workflow_review_flow.py tests/test_workflow_post_review_flow.py` |
| Textual presenter/parser/helper/UI cache | `uv run pytest -q tests/test_textual_answer_commands.py tests/test_textual_command_parsers.py tests/test_textual_improve_commands.py tests/test_textual_local_commands.py tests/test_textual_resume_commands.py tests/test_textual_review_commands.py tests/test_textual_slash_command_router.py tests/test_textual_target_workspace.py tests/test_textual_smoke.py tests/test_textual_runtime.py tests/test_textual_workflow_controller.py` |
| Nexus execution/log performance | Run the touched cache test plus `uv run pytest -q tests/test_performance_harness.py` when a performance budget is involved. |
| Fake provider harness | `uv run pytest -q tests/test_fake_provider_harness.py` |
| Broad facade or shared model changes | `uv run python scripts/run_required_smoke_tests.py -q` |

Do not run the full suite after every small edit. Run the full suite when a
change crosses module boundaries or before release/version bumps.

### PR Required CI

Pull requests should run the required smoke set only:

```bash
uv run python scripts/run_required_smoke_tests.py --list
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
- Textual slash command parsers, router, local command state,
  answer/improve/resume/review result, and target workspace helpers
- terminal rendering smoke

The smoke runner validates missing and duplicate manifest entries before
invoking pytest, and `--list` prints the exact PR/publish smoke set used by CI.

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

`docs/plans/` still contains many one-PR implementation plans, but the
completed-plan index now maps the dense recent batches to durable documents.
Archive only by bundle/date after these checks:

- the related PRs are merged
- focused tests or required smoke cover the behavior
- a durable contract or maintenance summary exists
- `docs/plans/completed-index.md` records the archive reason

Current archived bundles include Textual presenters, Korean UX, render cache,
UI label/status, execution/review feedback, fake-provider baseline, and
post-review maintenance plans. Older architecture and migration plans remain in
the root until their context is summarized separately.

### Facade Drift

Keep auditing these files for private wrappers that only forward to a flow:

- `src/trinity/workflow/engine.py`
- `src/trinity/orchestrator.py`
- `src/trinity/textual_app/app.py`

Current main snapshot after #540:

- `src/trinity/textual_app/app.py`: 3,091 lines
- `src/trinity/workflow/engine.py`: 625 lines
- `src/trinity/orchestrator.py`: 914 lines

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

Current glossary: `docs/development/korean-ui-glossary.md`.

### Cache Key Sprawl

The performance pass added many targeted cache keys. Keep them local while the
UI is still changing. Consolidate only where two widgets share the same snapshot
identity contract and the tests prove the contract.

Current guidance: `docs/development/nexus-render-cache-guidelines.md`.

## Next Release Goals

### Patch Train

- Keep patch releases for isolated bug fixes, smoke list adjustments, and
  low-risk wrapper removals.
- Require focused local tests plus `scripts/run_required_smoke_tests.py`.

### Next Minor

- Ship the CI/test strategy as the default engineering workflow.
- Maintain the completed-plan index for `docs/plans/` as more bundles are
  archived.
- Continue facade drift audits after each flow contract is documented.
- Continue splitting remaining high-churn Textual UI handlers after
  target/resume/answer/review/improve, route snapshot, and workspace helpers
  have been separated.
- Keep `WorkflowEngine` post-review and review repair helpers behind flow
  modules, and remove only wrappers that no longer carry behavior.
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
