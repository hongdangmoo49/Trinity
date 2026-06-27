# CI and Maintenance Strategy

This document records the maintenance plan after the large Nexus, workflow, UI,
and performance iteration. It is intentionally practical: use it to decide what
Codex runs locally, what GitHub Actions must block, what needs periodic cleanup,
and what the next release train should optimize.

## Current Evidence

- Baseline branch inspected: `main`
- Package version inspected: `1.0.596`
- Merged PR range reviewed: #90 through #692
- Baseline iteration reviewed: #90 through #426
- Maintenance refresh reviewed: #427 through #692
- Latest refresh reviewed: #692
- Required CI workflows inspected:
  - `.github/workflows/cross-platform-smoke.yml`
  - `.github/workflows/full-validation.yml`
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

### #541-#544: Maintenance Strategy and 2026-06-27 Plan Archive Closure

- Refreshed this strategy through #540 and recorded the Textual helper,
  Workflow facade cleanup, post-review, render-window, and smoke-runner bundles.
- Archived the completed 2026-06-27 Textual helper and Workflow facade cleanup
  plan bundles.
- Archived the remaining 2026-06-27 maintenance follow-up plans so root
  `docs/plans/` no longer contains dense one-PR plans from that day.

### #545-#548: CI Fast Path and Repository Hygiene

- Added `scripts/classify_ci_change.py` so PR CI can distinguish
  `docs_version_only` changes from changes that require the full required smoke
  pytest run.
- Kept wheel build and installed console-script smoke on the docs/version-only
  fast path while skipping only the pytest required smoke step.
- Verified the fast path with docs/version-only archive PRs where `Run required
  smoke tests` was skipped and `Validate docs/version-only fast path` passed.
- Added repository hygiene coverage to fail if Python bytecode, pytest cache,
  ruff cache, or `__pycache__` paths become tracked.
- Raised the package version from `1.0.443` to `1.0.451` across these focused
  patch PRs.

### #549-#551: Maintenance Refresh and Manual Full Validation

- Refreshed this strategy through #548 so the CI fast path, repository hygiene
  gate, and archive state were recorded in one durable maintenance document.
- Added a manual `Full validation` workflow for release candidates, broad
  refactors, and explicit confidence checks without making the full suite a
  required PR gate.
- Archived the manual full-validation plan after the workflow landed, leaving
  root `docs/plans/` clear of 2026-06-27 one-PR plans.
- Verified the docs/version-only fast path on the archive PR, where required
  smoke was skipped and fast-path validation passed on Linux, macOS, and
  Windows.
- Raised the package version from `1.0.451` to `1.0.454` across these focused
  patch PRs.

### #552-#555: Strategy Refresh, Nexus Runtime Archive, and Flow Accessors

- Refreshed this strategy through #551 after the manual full-validation and
  archive fast-path work landed.
- Archived the remaining 2026-06-25 Nexus runtime follow-up plans for activity
  frame gating, execution log windowing, retry filter no-op handling, review
  summary counts, and `.git` file branch detection.
- Added public workflow flow accessors for review results, post-review items,
  central continuation prompts, review package planning, and decision id
  generation while leaving private aliases for compatibility.
- Removed remaining cross-flow calls where one workflow flow reached into
  another flow's private helper.
- Verified the docs/archive PRs with the docs/version-only fast path and the
  code PRs with cross-platform required smoke.
- Raised the package version from `1.0.454` to `1.0.458` across these focused
  patch PRs.

### #557-#558: Textual Memory and Artifact Command Helpers

- Split `/memory` stats, compact, and cleanup presentation assembly from
  `textual_app/app.py` into `textual_app/memory_commands.py`.
- Split `/artifact` usage/error and artifact lookup presentation assembly into
  `textual_app/artifact_commands.py`.
- Added focused helper tests for both command helpers and included them in the
  required smoke manifest.
- Kept `TrinityTextualApp` responsible for routing and recording prepared local
  command results while moving command-specific presentation logic out of the
  app facade.
- Raised the package version from `1.0.459` to `1.0.461` across these focused
  patch PRs.

### #560: Textual Report Command Helper

- Split `/report` save/open presentation assembly from `textual_app/app.py`
  into `textual_app/report_commands.py`.
- Kept report export and route switching in `TrinityTextualApp`, while moving
  report-specific local command result metadata into a focused helper.
- Added focused report command helper tests and included them in the required
  smoke manifest.
- Fixed the new report helper test to avoid POSIX-only path assumptions after
  the Windows CI required-smoke run exposed the issue.
- Raised the package version from `1.0.462` to `1.0.463` in this patch PR.

### #562: Textual Context Command Helper

- Split `/context` route-specific presentation decisions from
  `textual_app/app.py` into `textual_app/context_commands.py`.
- Kept `TrinityTextualApp` responsible for the concrete side effects:
  notification, local command recording, modal display, and snapshot application.
- Added focused context command helper tests and included them in the required
  smoke manifest.
- Verified the change with focused Textual app coverage and cross-platform
  required smoke.
- Raised the package version from `1.0.464` to `1.0.465` in this patch PR.

### #564: Textual Save Command Helper

- Split `/save` automatic persistence messaging from `textual_app/app.py` into
  `textual_app/save_commands.py`.
- Added focused save command helper tests and included them in the required
  smoke manifest.
- Kept the app facade responsible for recording the prepared local command
  result while moving the command-specific message contract into a helper.
- Raised the package version from `1.0.466` to `1.0.467` in this patch PR.

### #566: Textual History Command Helper

- Split `/history` row calculation, empty state, action hint, table metadata,
  and markdown assembly from `textual_app/app.py` into
  `textual_app/history_commands.py`.
- Added focused history command helper tests and included them in the required
  smoke manifest.
- Kept the app facade responsible for refreshing the snapshot and recording the
  prepared local command result.
- Raised the package version from `1.0.468` to `1.0.469` in this patch PR.

### #568: Textual Questions Command Helper

- Split `/questions` title, body, empty state, action hint, table metadata,
  and `--select` body selection from `textual_app/app.py` into
  `textual_app/questions_commands.py`.
- Added focused questions command helper tests for empty, normal, select, and
  Korean presentation paths.
- Included the new helper tests in the required smoke manifest.
- Kept the app facade responsible for refreshing the snapshot, parsing select
  flags, and recording the prepared local command result.
- Raised the package version from `1.0.470` to `1.0.471` in this patch PR.

### #570: Textual Decisions Command Helper

- Split `/decisions` title, body, empty state, action hint, table metadata,
  and row assembly from `textual_app/app.py` into
  `textual_app/decisions_commands.py`.
- Added focused decisions command helper tests for empty, populated, and Korean
  presentation paths.
- Included the new helper tests in the required smoke manifest.
- Kept the app facade responsible for refreshing the snapshot and recording the
  prepared local command result.
- Raised the package version from `1.0.472` to `1.0.473` in this patch PR.

### #572: Textual Packages Command Helper

- Split `/packages` title, body, empty state, action hint, table metadata,
  and central/local row assembly from `textual_app/app.py` into
  `textual_app/packages_commands.py`.
- Added focused packages command helper tests for empty, central/local, and
  Korean presentation paths.
- Included the new helper tests in the required smoke manifest.
- Kept the app facade responsible for refreshing the snapshot and recording the
  prepared local command result.
- Raised the package version from `1.0.474` to `1.0.475` in this patch PR.

### #574: Textual Subtasks Command Helper

- Split `/subtasks` title, body, empty state, action hint, table metadata,
  and delegated subtask row assembly from `textual_app/app.py` into
  `textual_app/subtasks_commands.py`.
- Added focused subtasks command helper tests for empty, populated, and Korean
  presentation paths.
- Included the new helper tests in the required smoke manifest.
- Kept the app facade responsible for refreshing the snapshot and recording the
  prepared local command result.
- Raised the package version from `1.0.476` to `1.0.477` in this patch PR.

### #576: Textual Workflow Command Helper

- Split `/workflow` title, body, table metadata, and workflow snapshot row
  assembly from `textual_app/app.py` into `textual_app/workflow_commands.py`.
- Added focused workflow command helper tests for new workflow, populated
  snapshot counts, and Korean presentation paths.
- Included the new helper tests in the required smoke manifest.
- Kept the app facade responsible for refreshing the snapshot and recording the
  prepared local command result.
- Raised the package version from `1.0.478` to `1.0.479` in this patch PR.

### #578: Textual Status Command Adapter

- Split `/status` local command result creation behind
  `textual_app/status_commands.py` so `textual_app/app.py` only coordinates
  result storage, snapshot application, and modal display.
- Added focused status command adapter tests for basic snapshot, provider row,
  and Korean presentation paths.
- Included the new adapter tests in the required smoke manifest.
- Recorded the existing readiness label follow-up discovered while testing:
  non-unknown readiness values can request a missing `empty` status label.
- Raised the package version from `1.0.480` to `1.0.481` in this patch PR.

### #580: Status Readiness Label Fallback

- Fixed `/status` presenter rendering for non-unknown readiness values such as
  `ready` by using the existing `(none)` / `(없음)` fallback instead of a
  missing `empty` label.
- Strengthened status command tests to cover ready readiness rows in English
  and Korean.
- Preserved the status command adapter boundary introduced in #578 while
  removing the observed `KeyError` path.
- Raised the package version from `1.0.482` to `1.0.483` in this patch PR.

### #582: Textual Rounds Command Helper

- Split `/rounds` current value, updated value, and error presentation payloads
  from `textual_app/app.py` into `textual_app/rounds_commands.py`.
- Kept argument parsing and `max_deliberation_rounds` mutation in the app
  facade while moving command-specific body, action hint, severity, and table
  data assembly into the helper.
- Added focused rounds command helper tests for current, set, error, and Korean
  presentation paths.
- Included the new helper tests in the required smoke manifest.
- Raised the package version from `1.0.484` to `1.0.485` in this patch PR.

### #584: Textual Agent Command Helper

- Split `/agent` current settings, error, and update presentation payloads from
  `textual_app/app.py` into `textual_app/agent_commands.py`.
- Kept argument parsing and `agent.enabled` mutation in the app facade while
  moving command-specific body, action hint, severity, and table data assembly
  into the helper.
- Added focused agent command helper tests for current, error, update, and
  Korean presentation paths.
- Included the new helper tests in the required smoke manifest.
- Raised the package version from `1.0.486` to `1.0.487` in this patch PR.

### #586: Textual Caveman Command Helper

- Split `/caveman` current settings, updated settings, and error presentation
  payloads from `textual_app/app.py` into
  `textual_app/caveman_commands.py`.
- Kept argument parsing and `caveman_mode` / `caveman_intensity` mutation in
  the app facade while moving command-specific body, action hint, severity, and
  table data assembly into the helper.
- Added focused caveman command helper tests for current, set, error, and
  Korean presentation paths.
- Included the new helper tests in the required smoke manifest.
- Raised the package version from `1.0.488` to `1.0.489` in this patch PR.

### #588: Textual Help Command Helper

- Split registry-backed `/help` title, body, table column, and table row
  presentation assembly from `textual_app/app.py` into
  `textual_app/help_commands.py`.
- Kept `TrinityTextualApp` responsible only for recording the prepared local
  command result.
- Added focused help command helper tests for English and Korean output.
- Included the new helper tests in the required smoke manifest.
- Raised the package version from `1.0.490` to `1.0.491` in this patch PR.

### #590: Textual Ask Command Helper

- Split `/ask` error local command presentation assembly from
  `textual_app/app.py` into `textual_app/ask_commands.py`.
- Kept `/ask` parsing, workflow start, follow-up submission, target selection,
  and workflow outcome application in the app facade.
- Added focused ask command helper tests for English and Korean warning output.
- Included the new helper tests in the required smoke manifest.
- Raised the package version from `1.0.492` to `1.0.493` in this patch PR.

### #592: Textual Slash Error Command Helper

- Split slash command syntax-error and unknown-command presentation assembly
  from `textual_app/app.py` into `textual_app/slash_error_commands.py`.
- Kept slash command routing and local command result recording in the app
  facade while moving title, body, severity, suggestion table, and row assembly
  into the helper.
- Added focused slash error helper tests for syntax errors, unknown command
  suggestions, and Korean labels.
- Included the new helper tests in the required smoke manifest.
- Raised the package version from `1.0.494` to `1.0.495` in this patch PR.

### #594: Textual Model Settings Notification Helper

- Split model settings unavailable and updated notification presentation from
  `textual_app/app.py` into `textual_app/model_settings_commands.py`.
- Kept selector lookup, provider model refresh, modal opening, and model
  selection application in the app facade.
- Preserved the existing updated-notification behavior where severity is not
  explicitly passed to Textual.
- Added focused model settings notification helper tests for English and Korean
  labels.
- Included the new helper tests in the required smoke manifest.
- Raised the package version from `1.0.496` to `1.0.497` in this patch PR.

### #596: Textual Report Export Notification Helper

- Split report export unavailable and complete notification presentation from
  `textual_app/app.py` into `textual_app/report_commands.py`.
- Kept report markdown generation, file persistence, and `ReportScreen` export
  path updates in the app facade.
- Preserved the existing saved-report notification behavior where severity is
  not explicitly passed to Textual.
- Added focused report command tests for export unavailable, export complete,
  and Korean notification labels.
- Raised the package version from `1.0.498` to `1.0.499` in this patch PR.

### #598: Textual Target Command Helper

- Split `/target` current, clear, error, and set result presentation from
  `textual_app/app.py` into `textual_app/target_commands.py`.
- Kept target path parsing, control-repository confirmation, workspace
  preparation, controller target mutation, and workspace candidate sync in the
  app facade.
- Added focused target command helper tests for English and Korean output,
  warning states, and target workspace table rows.
- Included the new helper tests in the required smoke manifest.
- Raised the package version from `1.0.500` to `1.0.501` in this patch PR.

### #600: Textual Resume Command Helper

- Split `/resume` no-saved, archive picker, cancel, and result presentation
  from `textual_app/app.py` into `textual_app/resume_commands.py`.
- Kept archive lookup, picker modal display, workflow resume execution, outcome
  application, and Nexus route switching in the app facade.
- Preserved the existing resume outcome flag and continue-decision helpers.
- Expanded focused resume command helper tests for empty, archive, cancel, and
  result presentation paths.
- Raised the package version from `1.0.502` to `1.0.503` in this patch PR.

### #602: Textual Execute Command Helper

- Split `/execute` result and `/execute-retry` no-package presentation from
  `textual_app/app.py` into `textual_app/execute_commands.py`.
- Reused the same retry no-package presentation helper for Nexus Execution
  Matrix notifications and slash command local results.
- Added focused execute command helper tests for empty messages, finish-planning
  output, retry no-package output, and Korean labels.
- Included the new helper tests in the required smoke manifest.
- Raised the package version from `1.0.504` to `1.0.505` in this patch PR.

### #604: Textual Review and Improve Command Helpers

- Split `/review` result local command payload construction from
  `textual_app/app.py` into `textual_app/review_commands.py`.
- Split `/improve` result local command payload construction from
  `textual_app/app.py` into `textual_app/improve_commands.py`.
- Kept workflow outcome application and controller request orchestration in the
  app facade.
- Expanded focused review and improve command tests to cover title, body,
  severity, table rows, and action hints.
- Raised the package version from `1.0.506` to `1.0.507` in this patch PR.

### #606: Textual Answer Command Helper

- Split `/answer` parse-error local command payload construction from
  `textual_app/app.py` into `textual_app/answer_commands.py`.
- Split `/answer` workflow outcome local command payload construction from
  `textual_app/app.py` into `textual_app/answer_commands.py`.
- Kept question option dispatch, free-form answer dispatch, and workflow
  outcome application in the app facade.
- Expanded focused answer command tests to cover error/result payloads and
  Korean title output.
- Raised the package version from `1.0.508` to `1.0.509` in this patch PR.

### #608: Execution Matrix Review Notification Helper

- Split Execution Matrix review request notification payload construction from
  `textual_app/app.py` into `textual_app/review_commands.py`.
- Preserved the existing warning classification for no-pending, target
  workspace, and still-running messages.
- Kept review request dispatch and workflow outcome application in the app
  facade.
- Expanded focused review command tests to cover empty, warning, and info
  notification paths.
- Raised the package version from `1.0.510` to `1.0.511` in this patch PR.

### #610: Textual Target Cancel Snapshot Helper

- Split target workspace confirmation cancel local command snapshot
  construction from `textual_app/app.py` into `textual_app/target_commands.py`.
- Reused the helper for Nexus workspace selection, execution preflight, and
  `/target` confirmation cancel paths.
- Preserved existing selection and preflight cancel copy, warning severity, and
  empty-state behavior.
- Expanded focused target command tests to cover selection, preflight, and
  Korean cancel snapshot outputs.
- Raised the package version from `1.0.512` to `1.0.513` in this patch PR.

### #612: Textual Execution Recovery Snapshot Helper

- Split interrupted execution recovery local command snapshot construction
  from `textual_app/app.py` into `textual_app/execute_commands.py`.
- Kept the app facade responsible for recording the local command snapshot.
- Preserved existing recovery title, body, action hint, severity, and table row
  output.
- Expanded focused execute command tests to cover recovery snapshots and Korean
  title/table column output.
- Raised the package version from `1.0.514` to `1.0.515` in this patch PR.

### #614: Textual Review Repair Helpers

- Split review repair blocked package id lookup from `textual_app/app.py` into
  `textual_app/review_commands.py`.
- Split review repair local command snapshot construction from
  `textual_app/app.py` into `textual_app/review_commands.py`.
- Kept repair action routing, retry decisions, and local command recording in
  the app facade.
- Expanded focused review command tests to cover blocked id merging, repair
  snapshots, and Korean repair labels.
- Raised the package version from `1.0.516` to `1.0.517` in this patch PR.

### #616: Textual Local Command Presentation Helper

- Split local slash command snapshot construction from `textual_app/app.py`
  into `textual_app/local_commands.py`.
- Split local command route notification payload construction from
  `textual_app/app.py` into `textual_app/local_commands.py`.
- Kept local command persistence, snapshot application, modal display, and
  `notify` dispatch in the app facade.
- Expanded focused local command tests to cover snapshot payloads,
  notification severity, and Korean notification titles.
- Raised the package version from `1.0.518` to `1.0.519` in this patch PR.

### #618: Textual Workflow Outcome Notification Helper

- Split workflow outcome notification body construction from
  `textual_app/app.py` into `textual_app/workflow_commands.py`.
- Removed the final direct `textual_presenters` import and call from the
  Textual app facade.
- Kept workflow outcome application, Nexus refresh, execution screen refresh,
  and notification dispatch in the app facade.
- Expanded focused workflow command tests to cover outcome notification body
  rendering.
- Raised the package version from `1.0.520` to `1.0.521` in this patch PR.

### #620: Textual Provider Model Discovery Helper

- Split provider model discovery fan-out from `textual_app/app.py` into
  `textual_app/model_discovery.py`.
- Split changed-choice calculation so the app facade only applies changed
  model choices to Start, Nexus, and model settings screens.
- Added focused helper tests for completion-order yielding, failure/empty-result
  handling, and unchanged-choice filtering.
- Added `tests/test_textual_model_discovery.py` to the required smoke manifest.
- Raised the package version from `1.0.522` to `1.0.523` in this patch PR.

### #622: Textual Report Export Helper

- Split Markdown report export building and file writing from
  `textual_app/app.py` into `textual_app/report_export.py`.
- Kept report route state, export path display, and notification dispatch in
  the Textual app facade.
- Added focused helper tests for snapshot export writing, Korean labels, and
  no-data export behavior.
- Added `tests/test_textual_report_export.py` to the required smoke manifest.
- Raised the package version from `1.0.524` to `1.0.525` in this patch PR.

### #624: Textual Agent Command Helper

- Split `/agent` slash command parsing, state mutation, and presentation
  selection from `textual_app/app.py` into `textual_app/agent_commands.py`.
- Kept local command result recording in the Textual app facade.
- Expanded focused agent command tests to cover current settings, session-only
  enable changes, and error input without mutation.
- Raised the package version from `1.0.526` to `1.0.527` in this patch PR.

### #626: Textual Ask Command Action Helper

- Split `/ask` slash command parse-result normalization into
  `textual_app/ask_commands.py`.
- Converted valid `/ask` input into explicit `error`, `start`, or `follow_up`
  actions before the Textual app executes workflow side effects.
- Removed direct `parse_ask_args` and ask error presentation calls from
  `textual_app/app.py`.
- Expanded focused ask command tests to cover start route, follow-up route, and
  invalid agent input.
- Raised the package version from `1.0.528` to `1.0.529` in this patch PR.

### #628: Textual Caveman Command Helper

- Split `/caveman` slash command parsing, session-only state mutation, and
  presentation selection from `textual_app/app.py` into
  `textual_app/caveman_commands.py`.
- Kept local command result recording in the Textual app facade.
- Expanded focused caveman command tests to cover current settings, mode and
  intensity updates, and error input without mutation.
- Raised the package version from `1.0.530` to `1.0.531` in this patch PR.

### #630: Textual Rounds Command Helper

- Split `/rounds` slash command parsing, session-only state mutation, and
  presentation selection from `textual_app/app.py` into
  `textual_app/rounds_commands.py`.
- Kept local command result recording in the Textual app facade.
- Expanded focused rounds command tests to cover current value, round count
  updates, and error input without mutation.
- Raised the package version from `1.0.532` to `1.0.533` in this patch PR.

### #632: Textual Ask Command Runner

- Split valid `/ask` action execution from `textual_app/app.py` into
  `textual_app/ask_commands.py`.
- Moved Nexus agent selection, start prompt initialization, safe start
  workspace calculation, and workflow controller calls behind
  `run_ask_command`.
- Kept workflow outcome application, target preflight memory, workspace picker
  opening, and route switching in the Textual app facade.
- Expanded focused ask command tests to cover start execution, control-repo
  workspace skipping, and follow-up execution.
- Raised the package version from `1.0.534` to `1.0.535` in this patch PR.

### #634: Textual Answer Command Runner

- Split valid `/answer` execution routing from `textual_app/app.py` into
  `textual_app/answer_commands.py`.
- Moved parse-error handling, numbered option routing, free-form answer
  routing, and outcome message payload assembly behind focused answer command
  helpers.
- Kept workflow outcome application and local command result recording in the
  Textual app facade.
- Expanded focused answer command tests to cover parse errors, option routing,
  next-answer routing, and explicit question answers.
- Raised the package version from `1.0.536` to `1.0.537` in this patch PR.

### #636: Textual Target Command Action Helper

- Split `/target` input normalization from `textual_app/app.py` into
  `textual_app/target_commands.py`.
- Added `record`, `clear`, `confirm`, and `set` target command actions so the
  Textual app facade only performs workflow side effects and modal routing.
- Split target workspace preparation failure handling and set-result
  presentation into focused target command helpers.
- Expanded focused target command tests to cover platform-neutral path output,
  clear/current routing, control-repo confirmation, external set routing, and
  preparation errors.
- Raised the package version from `1.0.538` to `1.0.539` in this patch PR.

### #638: Textual Report Command Runner

- Split `/report` save/open routing and parser usage from
  `textual_app/app.py` into `textual_app/report_commands.py`.
- Added a report command runner that calls the export callback only for
  `/report save` and keeps `/report` open handling snapshot-only.
- Kept snapshot refresh, local command recording, and report route switching in
  the Textual app facade.
- Expanded focused report command tests to cover save exporter routing and
  open-without-export behavior.
- Raised the package version from `1.0.540` to `1.0.541` in this patch PR.

### #640: Textual Ask Command Effect Helper

- Split `/ask` run-result effect derivation from `textual_app/app.py` into
  `textual_app/ask_commands.py`.
- Added a focused effect helper for initial prompt storage, target preflight
  memory, Nexus route switching, and workspace picker display decisions.
- Kept concrete UI mutations in the Textual app facade while reducing
  `_handle_textual_ask_command` from 40 lines to 19 lines.
- Expanded focused ask command tests to cover start-route effects,
  follow-up workspace picker effects, and no-picker follow-up effects.
- Raised the package version from `1.0.542` to `1.0.543` in this patch PR.

### #642: Textual Review Repair Action Helper

- Split Nexus review repair action normalization from `textual_app/app.py` into
  `textual_app/review_commands.py`.
- Moved retry package id collection behind `review_repair_action` so the app
  receives a normalized repair action and focused package ids.
- Split retry-once UI application into `_retry_review_repair_action`, leaving
  `_handle_review_repair_action` focused on action dispatch.
- Expanded focused review command tests to cover known repair actions and
  unknown-action ignore behavior.
- Raised the package version from `1.0.544` to `1.0.545` in this patch PR.

### #644: Textual Context Snapshot Update Helper

- Split `/context` local command result replacement and snapshot update logic
  from `textual_app/app.py` into `textual_app/context_commands.py`.
- Kept concrete notify, modal, and workflow outcome side effects in the Textual
  app facade.
- Added focused context command tests for skipping presentations without
  results and replacing an existing context local command result.
- Reduced `_handle_textual_context_command` from 41 lines to 10 lines.
- Raised the package version from `1.0.546` to `1.0.547` in this patch PR.

### #646: Textual Resume Command Action Helper

- Split `/resume` argument and archive-list action selection from
  `textual_app/app.py` into `textual_app/resume_commands.py`.
- Added a resume workflow effect helper for Nexus route switching, execution
  recovery presentation, and context refresh decisions after resume.
- Kept concrete modal display, local command recording, and workflow outcome
  application in the Textual app facade.
- Expanded focused resume command tests to cover no-saved, picker, explicit
  selector, failed resume, continued resume, and execution recovery effects.
- Raised the package version from `1.0.548` to `1.0.549` in this patch PR.

### #648: Textual Answer Command Apply Helper

- Split `/answer` local command result recording into
  `_record_answer_command_presentation`.
- Split `/answer` workflow outcome application and message result handling into
  `_apply_textual_answer_run`.
- Kept answer parsing and workflow controller routing behind
  `textual_app/answer_commands.py`.
- Reduced `_handle_textual_answer_command` from 32 lines to 10 lines.
- Raised the package version from `1.0.550` to `1.0.551` in this patch PR.

### #650: Textual Execute Command Effect Helper

- Split `/execute` argument parsing and workflow execution request routing into
  `run_execute_command`.
- Added `execute_command_effect` to derive execution recovery display, local
  command presentation, and workspace picker effects from workflow outcomes.
- Kept concrete recovery presentation, local command recording, and workspace
  picker opening in the Textual app facade.
- Expanded focused execute command tests to cover runner routing, recovery
  priority, workspace picker effects, and no-op empty-message behavior.
- Raised the package version from `1.0.552` to `1.0.553` in this patch PR.

### #652: Textual Workspace Preflight Effect Helper

- Split workspace preflight continuation planning from `textual_app/app.py`
  into `textual_app/target_workspace.py`.
- Added helper state for fresh execution vs pending execution retry, preserving
  selected retry package ids.
- Added workspace preflight outcome effects for execution recovery display and
  execution route switching.
- Reduced `_continue_workspace_preflight` from 30 lines to 13 lines.
- Raised the package version from `1.0.554` to `1.0.555` in this patch PR.

### #654: Textual Context Presentation Effect Helper

- Split `/context` presentation-to-UI-effect derivation from
  `textual_app/app.py` into `textual_app/context_commands.py`.
- Added `ContextCommandEffect` and `context_command_effect` so notify, record,
  modal, workflow outcome, and no-op paths are testable without the Textual app.
- Kept concrete Textual side effects in the app facade while moving local
  command snapshot update selection into the helper layer.
- Reduced `_apply_textual_context_presentation` from 34 lines to 11 lines.
- Raised the package version from `1.0.556` to `1.0.557` in this patch PR.

### #656: Textual Local Command Result Effect Helper

- Split local slash-command result rendering state calculation from
  `textual_app/app.py` into `textual_app/local_commands.py`.
- Added `LocalCommandResultEffect` and `local_command_result_effect` so result
  replacement, snapshot refresh, modal routing, and notification payloads are
  testable without the Textual app.
- Kept concrete modal, workflow outcome, and notification side effects in the
  app facade.
- Reduced `_present_local_command_result` from 28 lines to 18 lines.
- Raised the package version from `1.0.558` to `1.0.559` in this patch PR.

### #658: Textual Execution Retry Request Effect Helper

- Split Execution Matrix retry request UI effect derivation from
  `textual_app/app.py` into `textual_app/execute_commands.py`.
- Added `ExecutionRetryRequestEffect` and `execution_retry_request_effect` so
  retry modal vs no-package warning behavior is testable without the Textual
  app.
- Kept preview execution retry side effects and concrete modal/notification
  dispatch in the app facade.
- Reduced `on_execution_matrix_screen_retry_requested` from 29 lines to 16
  lines.
- Raised the package version from `1.0.560` to `1.0.561` in this patch PR.

### #660: Textual Target Workspace Apply Effect Helper

- Split target workspace application state derivation from
  `textual_app/app.py` into `textual_app/target_commands.py`.
- Added `TargetWorkspaceApplyEffect` and `target_workspace_apply_effect` so
  workflow outcome snapshots, fallback snapshots, and target set presentation
  are testable without the Textual app.
- Kept controller mutation, confirmed preflight memory, candidate sync, and
  local command recording in the app facade.
- Reduced `_apply_textual_target_workspace` from 28 lines to 19 lines.
- Raised the package version from `1.0.562` to `1.0.563` in this patch PR.

### #662: Textual Target Command Effect Helper

- Split `/target` command action-to-app-effect derivation from
  `textual_app/app.py` into `textual_app/target_commands.py`.
- Added `TargetCommandEffect` and `target_command_effect` so record, clear,
  confirm, set, and no-op paths are testable without the Textual app.
- Kept current target lookup, controller mutation, confirmation modal routing,
  and workspace preparation side effects in the app facade.
- Reduced `_handle_textual_target_command` from 26 lines to 10 lines.
- Raised the package version from `1.0.564` to `1.0.565` in this patch PR.

### #664: Textual Start Submission Effect Helper

- Split Start screen prompt submission state derivation from
  `textual_app/app.py` into `textual_app/ask_commands.py`.
- Added `StartSubmissionEffect` and `start_submission_effect` so prompt,
  workspace candidate selection, safe target workspace, agent selection, and
  model override state are testable without the Textual app.
- Split the app-side Start submission application into UI preparation,
  controller invocation, and workflow outcome application helpers.
- Reduced `on_start_screen_submitted` from 26 lines to 11 lines.
- Raised the package version from `1.0.566` to `1.0.567` in this patch PR.

### #666: Textual Execute Retry Command Effect Helper

- Reused `execution_retry_request_effect` for `/execute-retry` slash command
  UI routing.
- Split no-package local command recording and retry modal opening into focused
  helpers shared with the Execution Matrix retry path.
- Kept preview execution retry and snapshot refresh side effects in the app
  facade.
- Reduced `_handle_textual_execute_retry_command` from 26 lines to 11 lines.
- Raised the package version from `1.0.568` to `1.0.569` in this patch PR.

### #668: Textual Model Settings Modal Effect Helper

- Split model settings modal request derivation from `textual_app/app.py` into
  `textual_app/model_settings_commands.py`.
- Added `ModelSettingsModalRequest` and `model_settings_modal_request` so
  unavailable notifications, discovered model choice merging, and selected
  model state are testable without the Textual app.
- Kept provider model refresh and concrete modal/notification side effects in
  the app facade.
- Reduced `_open_model_settings_modal` from 25 lines to 11 lines.
- Raised the package version from `1.0.570` to `1.0.571` in this patch PR.

### #670: Textual Report Export Effect Helper

- Split Markdown report export UI effect derivation from `textual_app/app.py`
  into `textual_app/report_commands.py`.
- Added `ReportExportEffect` and `report_export_effect` so export failure
  notifications and successful report path display are testable without the
  Textual app.
- Kept Markdown file writing and concrete report screen/notification side
  effects in the app facade.
- Reduced `_export_report_markdown` from 25 lines to 10 lines.
- Raised the package version from `1.0.572` to `1.0.573` in this patch PR.

### #672: Textual Status Command Effect Helper

- Split `/status` result generation and local command snapshot updates from
  `textual_app/app.py` into `textual_app/status_commands.py`.
- Added `status_command_effect` so start-route modal routing and non-start
  snapshot updates are testable without the Textual app.
- Kept the concrete `StatusCommandModal` and workflow outcome side effects in
  the app facade.
- Reduced `_show_textual_status` from 24 lines to 14 lines.
- Raised the package version from `1.0.574` to `1.0.575` in this patch PR.

### #674: Textual Improve Command Effect Helper

- Split `/improve` outcome-message presentation from `textual_app/app.py` into
  `textual_app/improve_commands.py`.
- Added `ImproveCommandEffect` and `improve_command_effect` so empty-message,
  info, and warning presentations are testable without the Textual app.
- Kept workflow controller invocation, workflow outcome application, and
  concrete slash-command recording in the app facade.
- Reduced `_handle_textual_improve_command` from 23 lines to 13 lines.
- Raised the package version from `1.0.576` to `1.0.577` in this patch PR.

### #676: Textual Context Effect Apply Helpers

- Split Textual `/context` effect application branches in `textual_app/app.py`
  into focused notify, record, and snapshot apply helpers.
- Kept the existing pure `ContextCommandEffect` derivation and Textual side
  effects unchanged.
- Reduced `_apply_textual_context_effect` from 25 lines to 8 lines.
- Raised the package version from `1.0.578` to `1.0.579` in this patch PR.

### #678: Textual Execute Effect Apply Helpers

- Split Textual `/execute` effect application branches in `textual_app/app.py`
  into focused recovery, slash-result, and workspace-picker apply helpers.
- Kept the existing pure `execute_command_effect` derivation and execute
  workflow behavior unchanged.
- Reduced `_apply_textual_execute_effect` from 23 lines to 10 lines.
- Raised the package version from `1.0.580` to `1.0.581` in this patch PR.

### #680: Textual Review Repair Action Apply Helpers

- Split Nexus review repair action application in `textual_app/app.py` from
  action normalization into focused apply helpers.
- Kept open review, retry once, mark done, and stop behavior unchanged.
- Reduced `_handle_review_repair_action` from 23 lines to 8 lines.
- Raised the package version from `1.0.582` to `1.0.583` in this patch PR.

### #682: Textual Target Workspace Apply Helpers

- Split target workspace preparation handling in `textual_app/app.py` from
  concrete workspace application.
- Added focused helpers for preparation warning recording and resolved path
  application.
- Reduced `_set_textual_target_workspace` from 22 lines to 10 lines.
- Raised the package version from `1.0.584` to `1.0.585` in this patch PR.

### #684: Textual Execute Retry Selected Apply Helpers

- Split execution retry modal selection handling in `textual_app/app.py` from
  retry confirmation outcome application.
- Added focused helpers for target-workspace-required outcomes and
  execution-requested outcomes.
- Added direct app coverage for workspace picker and execution route behavior
  after retry selection.
- Reduced `_on_execute_retry_selected` from 22 lines to 11 lines.
- Raised the package version from `1.0.586` to `1.0.587` in this patch PR.

### #686: Textual Workflow Outcome Apply Helpers

- Split `TextualWorkflowOutcome` application in `textual_app/app.py` into
  focused snapshot storage, Nexus update, Execution update, notification, and
  polling helpers.
- Kept hidden Nexus render avoidance, execution route refresh, notification,
  and polling behavior unchanged.
- Reduced `_apply_workflow_outcome` from 22 lines to 6 lines.
- Raised the package version from `1.0.588` to `1.0.589` in this patch PR.

### #688: Textual Questions Command Apply Helper

- Split `/questions` argument interpretation from `textual_app/app.py` into
  `textual_app/questions_commands.py`.
- Added helpers for `--select`/`-s` detection and argument-driven presentation
  creation.
- Reduced `_handle_textual_questions_command` from 21 lines to 12 lines.
- Raised the package version from `1.0.590` to `1.0.591` in this patch PR.

### #690: Textual Workspace Preflight Continuation Apply Helper

- Split workspace preflight continuation controller actions in
  `textual_app/app.py` from workflow outcome and preflight UI effect
  application.
- Kept target workspace persistence, retry continuation, fresh execution,
  execution recovery, and execution route behavior unchanged.
- Reduced `_continue_workspace_preflight_plan` from 21 lines to 11 lines.
- Raised the package version from `1.0.592` to `1.0.593` in this patch PR.

### #692: Textual Slash Command Result Recording Wrapper

- Slimmed `_record_slash_command_result` in `textual_app/app.py` so snapshot
  option handling is delegated to `local_command_snapshot`.
- Kept existing slash command result options, start modal behavior, local
  command recording, and notification behavior unchanged.
- Reduced `_record_slash_command_result` from 31 lines to 15 lines.
- Raised the package version from `1.0.594` to `1.0.595` in this patch PR.

This refresh moved the project further from "large batch of one-PR plans" to a
smaller set of durable maintenance documents and focused archive bundles. Root
`docs/plans/` no longer contains 2026-06-27 one-PR plans. Older architecture
and migration plans remain in the root; archive only the groups that have a
current contract document, merged PR evidence, and focused test coverage.

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
- `src/trinity/textual_app/agent_commands.py`, `answer_commands.py`,
  `ask_commands.py`, `caveman_commands.py`, `local_commands.py`,
  `model_discovery.py`, `report_export.py`, `rounds_commands.py`,
  `slash_command_router.py`, and `target_workspace.py` own focused command
  handling and command execution helpers, local command state, provider model
  discovery fan-out, report export generation, slash dispatch metadata, and
  target workspace path helpers.
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
  - `tests/test_textual_ask_commands.py`
  - `tests/test_textual_answer_commands.py`
  - `tests/test_textual_caveman_commands.py`
  - `tests/test_textual_command_parsers.py`
  - `tests/test_textual_improve_commands.py`
  - `tests/test_textual_local_commands.py`
  - `tests/test_textual_model_discovery.py`
  - `tests/test_textual_report_export.py`
  - `tests/test_textual_resume_commands.py`
  - `tests/test_textual_review_commands.py`
  - `tests/test_textual_rounds_commands.py`
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
| Textual presenter/parser/helper/UI cache | `uv run pytest -q tests/test_textual_ask_commands.py tests/test_textual_answer_commands.py tests/test_textual_caveman_commands.py tests/test_textual_command_parsers.py tests/test_textual_improve_commands.py tests/test_textual_local_commands.py tests/test_textual_model_discovery.py tests/test_textual_report_export.py tests/test_textual_resume_commands.py tests/test_textual_review_commands.py tests/test_textual_rounds_commands.py tests/test_textual_slash_command_router.py tests/test_textual_target_workspace.py tests/test_textual_smoke.py tests/test_textual_runtime.py tests/test_textual_workflow_controller.py` |
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

The cross-platform workflow first classifies the changed files with
`scripts/classify_ci_change.py`. Documentation-only changes, optionally paired
with a package version-only bump in `pyproject.toml`, `uv.lock`, and
`src/trinity/__init__.py`, use the `docs_version_only` fast path: CI lists the
required smoke manifest and keeps the wheel/console-script smoke, but skips the
pytest required smoke run. Any code, test, workflow, script, dependency, or
non-version metadata change falls back to the full required smoke set.

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
- Textual slash command parsers, router, local command state, provider model
  discovery, report export,
  ask/answer/caveman/improve/resume/review/rounds result, and target workspace
  helpers
- terminal rendering smoke
- repository hygiene for tracked generated Python/cache artifacts

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

GitHub Actions also provides a manual `Full validation` workflow that runs the
same full suite on Ubuntu/Python 3.12 via `workflow_dispatch`. Use it before
release candidates and after broad refactors. Do not make the full suite a
required PR gate until the runtime cost is measured and accepted.

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
Nexus runtime followups, UI label/status, execution/review feedback,
fake-provider baseline, and
post-review maintenance, Textual helper continuation, Workflow facade cleanup,
and maintenance follow-up plans. Older architecture and migration plans remain
in the root until their context is summarized separately.

### Facade Drift

Keep auditing these files for private wrappers that only forward to a flow:

- `src/trinity/workflow/engine.py`
- `src/trinity/orchestrator.py`
- `src/trinity/textual_app/app.py`

Current main snapshot after #650:

- `src/trinity/textual_app/app.py`: 2,829 lines
- `src/trinity/workflow/engine.py`: 625 lines
- `src/trinity/orchestrator.py`: 914 lines

Wrapper removal is safe only when focused flow tests and required smoke tests
cover the public behavior.

### Legacy Runtime Surface

Audit `src/trinity/legacy/`, `src/trinity/tmux/`, and `src/trinity/tui/` before
removal. These may still be compatibility surfaces, so the first step is usage
mapping, not deletion.

Current audit: `docs/development/legacy-runtime-surface-audit.md`.

### Repository Hygiene

Generated Python artifacts such as `__pycache__`, `.pyc`, `.pytest_cache`, and
`.ruff_cache` must remain untracked. The required smoke suite includes a
repository hygiene test so generated files fail before they reach release or
publish branches.

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
- Keep using the docs/version-only CI fast path for plan/archive/version-only
  PRs and required smoke for code, test, workflow, dependency, and non-version
  metadata changes.
- Keep repository hygiene in required smoke so generated Python/cache artifacts
  do not re-enter tracked files.

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
