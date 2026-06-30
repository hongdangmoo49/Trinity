# CI and Maintenance Strategy

This document records the maintenance plan after the large Nexus, workflow, UI,
and performance iteration. It is intentionally practical: use it to decide what
Codex runs locally, what GitHub Actions must block, what needs periodic cleanup,
and what the next release train should optimize.

## Current Evidence

- Baseline branch inspected: `main`
- Package version inspected: `1.0.920`
- Merged PR range reviewed: #90 through #1081
- Baseline iteration reviewed: #90 through #426
- Maintenance refresh reviewed: #427 through #1081
- Latest refresh reviewed: #1081
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

### #694: Textual Route Switch Preparation Helpers

- Split `switch_to` route preparation in `textual_app/app.py` into focused
  report route, execution route, and after-switch refresh helpers.
- Kept report preparation, execution snapshot application, route switching,
  and Nexus refresh scheduling behavior unchanged.
- Reduced `switch_to` from 25 lines to 5 lines.
- Raised the package version from `1.0.596` to `1.0.597` in this patch PR.

### #696: Textual Workbench Screen Specs

- Split Textual workbench screen construction from
  `_install_workbench_screens` into `textual_app/workbench_screens.py`.
- Kept Start, Nexus, Settings, Execution, and Report screen install order and
  constructor state unchanged.
- Added direct helper coverage for route order, screen types, language,
  settings store, and workspace candidate propagation.
- Reduced `_install_workbench_screens` from 22 lines to 13 lines.
- Raised the package version from `1.0.598` to `1.0.599` in this patch PR.

### #698: Textual Model Settings Modal Apply Helpers

- Split `_apply_model_settings_modal_request` in `textual_app/app.py` into
  notification and modal push helpers.
- Kept unavailable notification, modal construction, model choice data, and
  settings apply callback behavior unchanged.
- Reduced `_apply_model_settings_modal_request` from 21 lines to 8 lines.
- Raised the package version from `1.0.600` to `1.0.601` in this patch PR.

### #700: Textual Target Command Effect Apply Helpers

- Split target command effect application in `textual_app/app.py` into clear
  target workspace and path action helpers.
- Kept target command presentation, target clear, control repo confirmation,
  and external workspace setup behavior unchanged.
- Reduced `_apply_textual_target_command_effect` from 21 lines to 11 lines.
- Raised the package version from `1.0.602` to `1.0.603` in this patch PR.

### #702: Textual Controller Call Compatibility Helper

- Split controller method compatibility calls from `textual_app/app.py` into
  `textual_app/controller_calls.py`.
- Kept older test double compatibility, supported keyword filtering, and
  `**kwargs` passthrough behavior unchanged.
- Added focused coverage for supported keyword filtering, var-keyword methods,
  and signature lookup fallback.
- Removed `_call_controller_method` from `TrinityTextualApp`.
- Raised the package version from `1.0.604` to `1.0.605` in this patch PR.

### #704: Textual Slash Command Dispatch Apply Helper

- Split Textual slash command parse and dispatch-state resolution into
  `textual_slash_command_dispatch`.
- Kept non-command ignore, syntax error reporting, unknown command handling,
  route lookup, and handler dispatch behavior unchanged.
- Added focused coverage for non-command input, known command routing, syntax
  errors, and unknown command dispatch state.
- Reduced `_handle_textual_slash_command` from 20 lines to 6 lines.
- Raised the package version from `1.0.606` to `1.0.607` in this patch PR.

### #706: Textual Discovered Model Choice Surfaces

- Split discovered model choice application in `textual_app/app.py` into merge,
  screen surface sync, and model settings modal sync helpers.
- Kept unchanged-choice skipping, Start/Nexus recipient selector sync, and
  late-discovered model updates for an open `ModelSettingsModal` unchanged.
- Reduced `_apply_discovered_model_choices` from 18 lines to 8 lines.
- Raised the package version from `1.0.608` to `1.0.609` in this patch PR.

### #708: Textual Nexus Workspace Selection Confirm Helper

- Split Nexus workspace selection control-repo confirmation in
  `textual_app/app.py` into `_open_nexus_workspace_confirm_if_needed`.
- Kept external workspace selection, confirmation modal behavior, target
  workspace application, and no-execution side effect unchanged.
- Added direct coverage for selecting a control repo path from the Nexus
  workspace flow.
- Reduced `_on_nexus_workspace_selected` from 19 lines to 12 lines.
- Raised the package version from `1.0.610` to `1.0.611` in this patch PR.

### #710: Textual Target Workspace Apply Effect Helper

- Split target workspace effect construction in `textual_app/app.py` into
  `_build_textual_target_workspace_effect`.
- Kept target workspace controller calls, workflow outcome based presentation,
  workspace candidate updates, and target command recording behavior unchanged.
- Reduced `_apply_textual_target_workspace` from 19 lines to 12 lines.
- Raised the package version from `1.0.612` to `1.0.613` in this patch PR.

### #712: Textual Local Command Result Effect Helper

- Split local command result effect construction in `textual_app/app.py` into
  `_build_local_command_result_effect`.
- Kept local command event persistence, modal display, route snapshot updates,
  workflow outcome application, and notifications unchanged.
- Reduced `_present_local_command_result` from 18 lines to 15 lines.
- Raised the package version from `1.0.614` to `1.0.615` in this patch PR.

### #714: Textual Slash Command Presentation Recorder

- Added `_record_slash_command_presentation` in `textual_app/app.py` to share
  common local slash command presentation recording.
- Applied the helper to `/review`, `/rounds`, `/agent`, and `/caveman` command
  handlers without changing title, body, severity, table, or action hint
  propagation.
- Removed four repeated handler bodies from the large-method list and kept only
  the command-specific presentation builders in each handler.
- Raised the package version from `1.0.616` to `1.0.617` in this patch PR.

### #716: Textual Target Workspace Outcome Helper

- Split the target workspace controller call in `textual_app/app.py` into
  `_set_textual_target_workspace_outcome`.
- Kept target workspace effect construction, workflow outcome application,
  workspace candidate synchronization, and target command presentation recording
  unchanged.
- Removed `_build_textual_target_workspace_effect` from the large-method list.
- Raised the package version from `1.0.618` to `1.0.619` in this patch PR.

### #718: Textual Ask Command Run Helpers

- Split `/ask` handling in `textual_app/app.py` into
  `_build_textual_ask_command_action` and `_run_textual_ask_command`.
- Kept ask error presentation recording, Nexus selection application, workflow
  controller calls, and workspace candidate propagation unchanged.
- Removed `_handle_textual_ask_command` from the large-method list.
- Raised the package version from `1.0.620` to `1.0.621` in this patch PR.

### #720: TextualApp Init State Helpers

- Split `TrinityTextualApp.__init__` state setup into
  `_init_textual_navigation_state` and `_init_textual_runtime_state`.
- Kept parser patching, base Textual init, binding localization, config, route,
  workspace, snapshot, settings, workflow controller, polling, model discovery,
  local command, and retry state initialization unchanged.
- Removed the last 18-line-or-larger method from `textual_app/app.py`.
- Raised the package version from `1.0.622` to `1.0.623` in this patch PR.

### #722: Textual Slash Command Presentation Protocol

- Added `SlashCommandPresentationPayload` in `textual_app/app.py` to document
  the minimum payload contract for local slash command presentation recording.
- Narrowed `_record_slash_command_presentation` from `Any` to the new protocol
  while preserving optional field fallback behavior.
- Kept slash/local command recording and notification behavior unchanged.
- Raised the package version from `1.0.624` to `1.0.625` in this patch PR.

### #724: Textual Local Command Snapshot Option Types

- Added `LocalCommandSnapshotOptionValue` in `textual_app/app.py` to type the
  option values forwarded into local command snapshots.
- Narrowed `_record_slash_command_result` snapshot kwargs from `Any` to the new
  value alias and removed the remaining `Any` import from the module.
- Kept local/slash command snapshot generation behavior unchanged.
- Raised the package version from `1.0.626` to `1.0.627` in this patch PR.

### #726: Textual Workflow Running Helper

- Centralized workflow controller running-state checks in
  `_workflow_controller_is_running`.
- Reused the helper for workflow polling activity frame updates and quit
  confirmation modal running-state display.
- Preserved the existing `is_running` fallback behavior for controller
  compatibility.
- Raised the package version from `1.0.628` to `1.0.629` in this patch PR.

### #728: New/Existing Project Onboarding Redesign

- Added a design plan to separate Trinity's entry path for new projects and
  existing projects. The root plan file was removed later when the prompt-led
  Workbench contract superseded mode-led onboarding surfaces.
- Proposed explicit CLI surfaces for `trinity init --mode new`,
  `trinity init --mode existing`, and `trinity project analyze [PATH]`.
- Defined project intake artifacts under `.trinity/project-intake.json` and
  `.trinity/project-intake.md`.
- Chose workspace preflight Git status as the first low-risk implementation
  slice before larger onboarding UX changes.
- Raised the package version from `1.0.630` to `1.0.631` in this docs PR.

### #729: Workspace Preflight Git Status

- Replaced the fixed `Dirty worktree: unknown` preflight output with read-only
  `git status --porcelain` metadata.
- Displayed clean, changed, untracked, and non-Git workspace states in English
  and Korean.
- Kept execution gating unchanged: the Git state is informational and does not
  block execution.
- Expanded focused workspace picker tests for clean, changed, untracked, and
  non-Git render paths.
- Raised the package version from `1.0.631` to `1.0.632` in this patch PR.

### #731: Project Intake Writer

- Added `src/trinity/project_intake.py` as the shared read-only project intake
  contract for new/existing project onboarding.
- Added JSON and Markdown writers for `.trinity/project-intake.json` and
  `.trinity/project-intake.md`.
- Captured target workspace Git metadata, package manager hints, and suggested
  test commands without executing project commands.
- Reused the shared Git analysis from the workspace picker preflight.
- Added `tests/test_project_intake.py` and promoted project intake/workspace
  picker tests into the required smoke manifest.
- Raised the package version from `1.0.633` to `1.0.634` in this patch PR.

### #733: Project Analyze Command

- Added `trinity project analyze [PATH]` as the first CLI surface over the
  project intake contract.
- Required an initialized Trinity project so intake artifacts are written under
  the configured `.trinity` state directory.
- Added `--mode existing|new` and `--notes` options for onboarding context.
- Wrote `.trinity/project-intake.json` and `.trinity/project-intake.md` from
  the analyzed target workspace.
- Expanded CLI tests for the missing-init error path and successful intake
  artifact generation.
- Raised the package version from `1.0.635` to `1.0.636` in this patch PR.

### #735: Textual Target Workspace Labels

- Added `textual_app/workspace_labels.py` as the shared Start/Nexus target
  workspace label helper.
- Replaced generic `Workspace: ...` copy with explicit states for no target,
  planning target, and control repo target requiring confirmation before write.
- Applied the same English/Korean label contract to Start and Nexus.
- Added focused Start/Nexus label tests and included `tests/test_start_screen.py`
  in the required smoke manifest.
- Raised the package version from `1.0.637` to `1.0.638` in this patch PR.

### #737: Init Project Mode Intake

- Added `trinity init --mode existing|new` to record project onboarding mode
  during initialization.
- Built project intake metadata before init writes `.trinity` files so the
  captured Git/package state reflects the pre-init workspace.
- Wrote `.trinity/project-intake.json` and `.trinity/project-intake.md` after
  init completes when a mode is selected.
- Prompted for project mode in interactive init while keeping non-interactive
  init unchanged when `--mode` is omitted.
- Expanded CLI tests for mode intake writing and prompt policy.
- Raised the package version from `1.0.639` to `1.0.640` in this patch PR.

### #739: Project Intake Prompt Context

- Added project intake prompt block loading from `.trinity/project-intake.md`.
- Injected project intake context into DeliberationProtocol provider round
  prompts.
- Injected project intake context into WorkflowEngine central continuation
  prompts.
- Preserved existing prompt output when project intake is absent.
- Added intake/protocol/workflow tests and promoted `tests/test_protocol.py`
  into the required smoke manifest.
- Raised the package version from `1.0.641` to `1.0.642` in this patch PR.

### #741: Project New Command

- Added `trinity project new NAME` as the CLI path for creating a new target
  project workspace.
- Added `--parent PATH` and `--git/--no-git` options for parent-folder
  selection and optional Git initialization.
- Wrote project intake artifacts under Trinity state after creating the new
  workspace.
- Rejected existing project folders and nested project names to avoid accidental
  broad path creation.
- Expanded CLI tests for creation, Git init, missing Trinity project, and
  invalid target handling.
- Raised the package version from `1.0.643` to `1.0.644` in this patch PR.

### #743: Workspace Picker Intent Label

- Added a Workspace Picker preflight intent row to distinguish existing Git
  workspaces, existing directory workspaces, new workspace folders, missing
  paths, and invalid paths.
- Added English and Korean labels for the new intent states.
- Expanded workspace picker tests for existing, new, Git, invalid, and Korean
  render paths.
- Stabilized the recompose status-key test with a short polling helper for
  slower Windows Textual recompose timing.
- Raised the package version from `1.0.645` to `1.0.646` in this patch PR.

### #745: Project Intake Status Command

- Added `trinity project status` so users can inspect the currently recorded
  project intake before starting work.
- Guided missing-intake projects toward `trinity project analyze [PATH]` for
  existing projects or `trinity project new NAME` for new projects.
- Split saved intake analysis from current target workspace analysis in the CLI
  output.
- Added JSON loading support for `.trinity/project-intake.json`.
- Stabilized the Textual model discovery completion-order test with explicit
  thread synchronization for Windows CI.
- Raised the package version from `1.0.647` to `1.0.648` in this patch PR.

### #747: Textual Intake Workspace Default

- Made Textual startup prefer the persisted project intake target workspace
  when it still exists as a directory.
- Preserved launch-cwd fallback when intake is missing, invalid, stale, or not a
  directory.
- Added Start screen coverage proving the intake target appears as the initial
  planning target and is passed to execution startup.
- Aligned stale Textual label tests with the current `Planning target` /
  `계획 대상` wording.
- Raised the package version from `1.0.649` to `1.0.650` in this patch PR.

### #749: Project Onboarding Next Steps

- Added explicit next-step guidance to `trinity project new` and
  `trinity project analyze` completion output.
- Added missing-intake guidance telling users to analyze or create a project and
  then run `trinity`.
- Added active-intake guidance telling users to run `trinity` to start planning
  with the recorded target.
- Expanded CLI tests for the new guidance.
- Raised the package version from `1.0.651` to `1.0.652` in this patch PR.

### #751: Project Status JSON Output

- Added `trinity project status --json` for scripts and CI checks.
- Returned missing-intake next steps as JSON without rendering Rich panels.
- Returned saved project intake and current target workspace analysis in a
  stable JSON payload.
- Expanded CLI tests for missing-intake and active-intake JSON output.
- Raised the package version from `1.0.653` to `1.0.654` in this patch PR.

### #753: Project Status Refresh

- Added `trinity project status --refresh` to rewrite saved project intake from
  the current target workspace state.
- Preserved the existing intake mode, target workspace, and notes while
  refreshing package manager, test command, and Git metadata.
- Made `--refresh --json` report refresh status and updated intake artifact
  paths.
- Expanded CLI tests for panel and JSON refresh flows, including Windows-safe
  path assertions.
- Raised the package version from `1.0.655` to `1.0.656` in this patch PR.

### #755: Textual Project Intake Summary

- Added saved project intake summary labels to the Start and Nexus screens.
- Displayed project mode and detected test commands so users can confirm the
  new/existing project context before planning or execution.
- Added English and Korean labels for missing, invalid, and active intake
  states.
- Expanded Start/Nexus render tests for the new summary labels.
- Raised the package version from `1.0.657` to `1.0.658` in this patch PR.

### #757: Init Project Mode Next Steps

- Added next-step guidance to `trinity init --mode existing/new` summaries when
  project intake artifacts are written.
- Guided users to run `trinity project status` and then `trinity` immediately
  after init-mode onboarding.
- Expanded init CLI tests for the new guidance.
- Raised the package version from `1.0.659` to `1.0.660` in this patch PR.

### #759: Project Onboarding Status Guide

- Documented separate README flows for existing projects and new projects.
- Added user-facing guidance for `trinity project status --json` and
  `trinity project status --refresh`.
- Added `trinity project analyze`, `trinity project new`, and
  `trinity project status` to the README command tables.
- Raised the package version from `1.0.661` to `1.0.662` in this patch PR.

### #760: Workbench Project Intake Action Hints

- Expanded Start/Nexus project intake labels so missing intake states show
  immediate `trinity project analyze [PATH]` and `trinity project new NAME`
  next actions.
- Added invalid-intake recovery guidance for `.trinity/project-intake.json`.
- Added explicit Textual styles for project intake summary labels so longer
  guidance wraps below the action rows instead of competing with buttons.
- Expanded Start screen tests for missing-intake action hints.
- Raised the package version from `1.0.662` to `1.0.663` in this patch PR.

### #762: New Project Init Pending Intake

- Changed `trinity init --mode new` so it no longer records the current folder
  as the active target workspace.
- Deferred new-project intake artifact creation until
  `trinity project new NAME --parent PATH` creates the target project.
- Kept `trinity init --mode existing` behavior unchanged so existing projects
  still record the current folder immediately.
- Updated README/README.en to describe the pending-intake new project flow.
- Expanded init CLI tests for the deferred new-project intake behavior.
- Raised the package version from `1.0.664` to `1.0.665` in this patch PR.

### #764: Workbench Workspace Intake Sync

- Synced project intake artifacts when the Workbench starts planning from the
  default target workspace.
- Synced project intake artifacts after Start/Nexus workspace picker selection,
  execution preflight confirmation, `/ask` start commands, and `/target`
  application.
- Preserved `WorkspacePreflight.created` for newly created folders so
  Workbench-created projects are recorded with `mode=new`.
- Refreshed Start/Nexus project intake summary labels after successful intake
  writes.
- Expanded Textual app and workspace picker tests for existing and newly
  created workspace intake sync.
- Raised the package version from `1.0.666` to `1.0.667` in this patch PR.

### #766: Start Workspace Analysis CTA

- Added a Start screen `Analyze Workspace` / `작업 폴더 분석` button.
- Made the button write existing-project intake for the current safe target
  workspace and refresh the visible intake summary.
- Routed unsafe control-repo candidates to the workspace picker instead of
  silently doing nothing.
- Expanded Textual app tests for the direct analysis action and control-repo
  fallback path.
- Raised the package version from `1.0.668` to `1.0.669` in this patch PR.

### #768: Start Create Project CTA

- Added a Start screen `Create Project` / `새 프로젝트` button.
- Added an `open_new_folder` workspace picker option so the new-project CTA
  opens the folder-name prompt immediately.
- Reused the Workbench intake sync path so confirmed newly created folders are
  recorded as `mode=new`.
- Expanded Textual app tests for the Start create-project end-to-end flow.
- Raised the package version from `1.0.670` to `1.0.671` in this patch PR.

### #770: Start CTA Layout Density

- Stabilized Start screen CTA button widths for narrower terminal layouts.
- Added explicit spacing for `Select Workspace`, `Plan first`,
  `Analyze Workspace`, and `Create Project`.
- Allowed the workspace candidate label to shrink before it competes with the
  fixed-width action buttons.
- Added a Textual app regression test for Start CTA dimensions.
- Raised the package version from `1.0.672` to `1.0.673` in this patch PR.

### #772: Nexus Project Intake CTAs

- Added Nexus screen `Analyze Workspace` / `작업 폴더 분석` and
  `Create Project` / `새 프로젝트` actions so users can record target project
  context without returning to Start.
- Routed new-project creation through the workspace picker with the folder-name
  prompt opened immediately.
- Preferred the Nexus snapshot target over stale workspace candidates when the
  user analyzes the currently displayed target.
- Preserved `mode=new` intake after Nexus-created folders by applying target
  workspace state before the final intake sync.
- Expanded Textual app tests for direct Nexus analysis, snapshot target
  preference, and Nexus new-project intake.
- Raised the package version from `1.0.674` to `1.0.675` in this patch PR.

### #774: Project Intake Workspace Profile

- Extended project intake artifacts with read-only workspace profile fields:
  `dev_commands`, `build_commands`, `entrypoints`, `source_roots`, and
  `docs_found`.
- Added conservative Python, Node, Rust, Go, Java, and documentation detection
  so new/existing project starts give agents better orientation before planning
  or editing.
- Kept legacy `project-intake.json` files valid by loading missing profile
  fields as empty tuples.
- Added `docs/development/project-intake-workspace-profile.md` to document the
  profile contract and its non-execution safety boundary.
- Expanded ProjectIntake tests for Node/Python profile detection, Markdown/JSON
  serialization, and legacy intake compatibility.
- Raised the package version from `1.0.676` to `1.0.677` in this patch PR.

### #776: Project Intake Profile Summary

- Expanded Start/Nexus project intake summary labels so saved workspace profile
  data is visible in the workbench.
- Preserved the existing mode/test summary and appended `dev`, `build`,
  `entry`, and `docs` sections only when those profile values exist.
- Added compact value formatting so long profile lists show the first two
  values plus a remaining count.
- Added English and Korean label coverage for the expanded profile summary.
- Expanded Start screen label tests for profile-aware summaries.
- Raised the package version from `1.0.678` to `1.0.679` in this patch PR.

### #778: Project Intake Prompt Guidance

- Added mode-specific guidance to `Project Intake Context` when persisted
  intake JSON and Markdown are both available.
- Framed existing projects as established workspaces where agents should read
  docs, entrypoints, and source roots before proposing edits.
- Framed new projects as fresh workspaces where agents should confirm product
  goal, stack, and first milestone before scaffolding.
- Preserved legacy Markdown-only intake prompt behavior without extra guidance.
- Expanded ProjectIntake tests for existing/new prompt guidance and prompt
  context injection paths.
- Raised the package version from `1.0.680` to `1.0.681` in this patch PR.

### #780: Project Brief Intake Fields

- Added user-provided project brief fields to ProjectIntake:
  `product_goal`, `stack_preferences`, `first_milestone`, and `constraints`.
- Added `trinity project new` and `trinity project analyze` options for
  recording the brief: `--goal`, `--stack`, `--milestone`, and `--constraint`.
- Included the brief in project-intake JSON, Markdown, `project status`, and
  `project status --json` output.
- Preserved the saved brief when `trinity project status --refresh` refreshes
  filesystem-derived analysis.
- Kept legacy intake JSON compatible by loading missing brief fields as empty
  values.
- Raised the package version from `1.0.682` to `1.0.683` in this patch PR.

### #782: Workbench Project Brief Preservation

- Changed Workbench project-intake sync so it preserves saved project brief
  fields and notes when refreshing the same target workspace.
- Prevented stale brief data from being carried to a different target
  workspace.
- Reused the target path normalization helper so preservation works across
  equivalent path spellings.
- Expanded Textual app tests for same-target preservation and new-target
  non-carry behavior.
- Raised the package version from `1.0.684` to `1.0.685` in this patch PR.

### #784: Start Prompt Project Goal Seed

- Seeded the Start composer from saved ProjectIntake `product_goal` when the
  saved intake target matches the current workspace candidate.
- Kept target isolation by refusing to carry a product goal from a different
  target workspace.
- Added `initial_text` / `initial_prompt` plumbing through PromptComposer,
  StartScreen, and Workbench screen construction.
- Expanded Textual app and workbench screen tests for same-target prompt seeding
  and default empty prompts.
- Raised the package version from `1.0.686` to `1.0.687` in this patch PR.

### #786: Workbench Project Brief Editor

- Added Start/Nexus `Edit Brief` actions so users can edit project brief fields
  without switching back to CLI flags.
- Added a project brief modal for `product_goal`, `stack_preferences`,
  `first_milestone`, `constraints`, and `notes`.
- Wrote saved brief values back through project intake JSON/Markdown and
  refreshed Start/Nexus project-intake summaries immediately.
- Seeded the Start composer from a newly saved product goal when the composer is
  still empty and the saved target matches the active workspace candidate.
- Expanded Textual app tests for Start/Nexus brief editing, CTA dimensions, and
  summary label updates.
- Raised the package version from `1.0.688` to `1.0.689` in this patch PR.

### #788: Project Intake Discovery Fields

- Added saved product discovery fields to ProjectIntake:
  `project_type`, `target_users`, and `success_criteria`.
- Added `trinity project new/analyze` options for recording the fields:
  `--project-type`, `--target-users`, and `--success-criteria`.
- Preserved the discovery fields through `project status --refresh` and
  Workbench Start/Nexus intake synchronization.
- Expanded the Workbench `Edit Brief` modal and Start/Nexus intake summary
  labels so users can see the project type and target users before planning.
- Expanded ProjectIntake, CLI, Start/Nexus label, and Workbench modal tests.
- Raised the package version from `1.0.690` to `1.0.691` in this patch PR.

### #790: New Project Brief Readiness

- Added new-project brief readiness helpers for the minimum useful startup
  fields: goal, type, users, success, and milestone.
- Displayed `Brief readiness` in `trinity project new/analyze/status` output
  and exposed the same state in `project status --json`.
- Added Start/Nexus project-intake summary labels that show complete/missing
  brief state for new projects only.
- Kept existing projects free of readiness warnings so read-only workspace
  analysis remains the primary signal for that journey.
- Expanded ProjectIntake, CLI, and Start label tests for complete/missing
  readiness states.
- Raised the package version from `1.0.692` to `1.0.693` in this patch PR.

### #792: Project Intake Prompt Readiness Guidance

- Updated provider prompt guidance to use the same new-project brief readiness
  contract shown in CLI and Workbench summaries.
- Incomplete new-project briefs now instruct providers to confirm missing
  fields before scaffolding and avoid treating framework/UX choices as final.
- Complete new-project briefs now instruct providers to use recorded goal,
  type, users, success criteria, stack, milestone, and constraints as planning
  constraints.
- Existing-project prompts now treat saved brief fields as user intent while
  still requiring verification against detected docs and source.
- Expanded ProjectIntake prompt block tests for incomplete new-project,
  complete new-project, and existing-project brief guidance.
- Raised the package version from `1.0.694` to `1.0.695` in this patch PR.

### #794: Existing Project Git Summary Label

- Added saved Git state to Start/Nexus project-intake summaries for existing
  projects.
- Non-Git workspaces show `git: none`, clean repositories show branch + clean,
  and dirty repositories show branch plus saved dirty/untracked counts.
- Kept new-project summaries focused on brief readiness instead of Git safety
  labels.
- Expanded Start/Nexus label tests for non-Git summaries and dirty Git
  workspaces in English and Korean.
- Raised the package version from `1.0.696` to `1.0.697` in this patch PR.

### #796: Project Intake Source Roots Summary

- Added detected source roots to Start/Nexus project-intake summaries.
- Existing-project users can now confirm that Trinity found expected source and
  test directories before asking agents to plan or execute against the target.
- Kept the summary compact by reusing the existing two-value truncation format
  used by other workspace profile sections.
- Expanded Start/Nexus label tests for English and Korean source-root summary
  output.
- Raised the package version from `1.0.698` to `1.0.699` in this patch PR.

### #798: Project Brief Detail Summary

- Added saved success criteria, first milestone, stack preferences, and
  constraints to Start/Nexus project-intake summaries.
- New-project users can now verify the intended product direction before
  scaffolding instead of seeing only `brief: complete`.
- Existing-project users can also see saved user intent before agents plan
  against the codebase.
- Expanded English and Korean Start/Nexus label coverage for complete brief
  detail summaries.
- Raised the package version from `1.0.700` to `1.0.701` in this patch PR.

### #800: Project Intake Updated Date Summary

- Added saved analysis dates to Start/Nexus project-intake summaries as
  `updated: YYYY-MM-DD` / `갱신: YYYY-MM-DD`.
- Existing-project users can now see whether the saved workspace analysis is
  likely stale before planning or execution.
- Kept the display compact by deriving the date from the persisted
  `created_at` timestamp.
- Expanded Start/Nexus label tests for English and Korean updated-date output.
- Raised the package version from `1.0.702` to `1.0.703` in this patch PR.

### #802: Selected Workspace Missing Intake Guidance

- Updated missing project-intake Start/Nexus labels to include the selected
  workspace in the suggested `trinity project analyze <path>` command.
- Kept the generic existing/new project commands when no workspace is selected.
- Passed the Start workspace candidate and Nexus current workspace into the
  shared project-intake label helper.
- Expanded Start/Nexus label tests for selected-workspace missing-intake
  guidance.
- Raised the package version from `1.0.704` to `1.0.705` in this patch PR.

### #804: Project Intake Target Mismatch Summary

- Added Start/Nexus project-intake warnings when the saved intake target differs
  from the currently selected workspace.
- Kept matching-target summaries unchanged while surfacing stale or wrong-target
  intake state near the front of the summary.
- Reused the shared project-intake label helper so Start and Nexus show the same
  mismatch wording.
- Expanded Start/Nexus label tests for English and Korean mismatch output and
  matching-target suppression.
- Raised the package version from `1.0.706` to `1.0.707` in this patch PR.

### #806: Project Status Compact Summary

- Added a compact project-intake summary to `trinity project status` before the
  detailed saved/current analysis sections.
- Reused the same project-intake label formatter used by Start/Nexus so CLI and
  Workbench users see the same target, brief, test, and safety signals.
- Kept JSON status output unchanged while improving the human-readable status
  panel.
- Expanded CLI status tests for the new summary line and preserved Start/Nexus
  label coverage.
- Raised the package version from `1.0.708` to `1.0.709` in this patch PR.

### #808: Incomplete New Project Brief CTA

- Highlighted the Start/Nexus `Edit Brief` action when the selected workspace
  has a saved new-project intake with missing minimum brief fields.
- Returned the action to default priority once the minimum new-project brief is
  complete.
- Suppressed the highlight when the saved intake target differs from the current
  workspace to avoid steering users toward the wrong brief.
- Expanded Start/Nexus button variant tests and shared action-variant helper
  coverage.
- Raised the package version from `1.0.710` to `1.0.711` in this patch PR.

### #810: Sparse Existing Project Analysis Signal

- Added an `analysis: sparse` / `분석: 부족` compact-summary signal for
  existing-project intake when tests, source roots, and docs are all missing.
- Reused the shared summary formatter so Start/Nexus and `project status` show
  the same sparse-analysis warning.
- Kept new-project summaries focused on brief readiness rather than structure
  detection quality.
- Expanded Start/Nexus label tests for English and Korean sparse-analysis
  output.
- Raised the package version from `1.0.712` to `1.0.713` in this patch PR.

### #812: Sparse Analysis Missing Anchors

- Added missing-anchor details to compact sparse-analysis summaries.
- Start/Nexus and `trinity project status` now show
  `missing: tests, src, docs` / `누락: 테스트, 소스, 문서` when existing-project
  intake has no tests, source roots, or docs.
- Reused the shared project-intake formatter so Workbench and CLI stay aligned.
- Expanded Start/Nexus label tests for English and Korean sparse-analysis
  details.
- Raised the package version from `1.0.714` to `1.0.715` in this patch PR.

### #814: Stale Existing Project Analysis Signal

- Added a stale-analysis signal for existing-project intake older than 14 days.
- Start/Nexus and `trinity project status` now show
  `analysis: stale Nd` / `분석: 오래됨 N일` plus a
  `trinity project analyze <target>` refresh command.
- Reused the shared project-intake formatter so Workbench and CLI stay aligned.
- Added deterministic Start/Nexus label tests for English and Korean stale
  analysis output.
- Raised the package version from `1.0.716` to `1.0.717` in this patch PR.

### #816: New Project Brief Completion Next Steps

- Added missing-field completion commands to new-project brief next steps.
- `trinity project new`, `trinity project analyze --mode new`,
  `trinity project status`, and JSON status now reuse a shared next-step helper.
- Human CLI output renders long completion commands across multiple lines so
  options remain visible on narrow macOS and Windows terminals.
- Added CLI coverage for incomplete new-project brief guidance and preserved
  existing-project status next steps.
- Raised the package version from `1.0.718` to `1.0.719` in this patch PR.

### #818: Missing Project Intake Target Summary

- Added a `target missing` / `대상 없음` compact-summary signal when the saved
  project-intake target workspace no longer exists.
- Reused the shared project-intake formatter so Start/Nexus and
  `trinity project status` show the same missing-target warning.
- Added CLI status coverage for missing targets alongside Start/Nexus label
  coverage in English and Korean.
- Raised the package version from `1.0.720` to `1.0.721` in this patch PR.

### #820: Missing Target Recovery Next Steps

- Updated CLI status next steps so missing project-intake targets prefer
  recovery commands instead of sending users directly to `trinity`.
- Existing-project missing targets now guide users back to
  `trinity project analyze [PATH]`.
- New-project missing targets now guide users to recreate the folder with
  `trinity project new <name> --parent <path>`.
- Added CLI and JSON status coverage for both existing and new missing-target
  recovery paths.
- Raised the package version from `1.0.722` to `1.0.723` in this patch PR.

### #822: Workbench Project Intake Action Variants

- Highlighted Workbench `Analyze Workspace` when project intake needs recovery:
  missing selected-workspace analysis, mismatched target, sparse/stale existing
  analysis, unreadable intake, or a missing existing-project target.
- Highlighted `Create Project` when a saved new-project target no longer
  exists.
- Kept `Edit Brief` focused on incomplete new-project brief fields.
- Wired the shared action-variant helpers into Start and Nexus and refreshed
  button variants after intake changes.
- Added Start/Nexus helper and mounted-screen coverage for the new variants.
- Raised the package version from `1.0.724` to `1.0.725` in this patch PR.

### #824: Project Status JSON Compact Summary

- Added the shared compact project-intake summary to
  `trinity project status --json` under `project_intake.summary`.
- Let scripts and tools consume the same target, brief, sparse/stale, and
  missing-target readiness signals used by Start/Nexus and human CLI status.
- Added JSON status coverage for existing-project and missing-new-target
  summaries.
- Raised the package version from `1.0.726` to `1.0.727` in this patch PR.

### #826: Project Status JSON Action Metadata

- Added `project_intake.readiness` to `trinity project status --json` with
  target existence, sparse/stale analysis, missing new-project brief fields,
  and a structured recommended next action.
- Added `project_intake.action_variants` so scripts and UI surfaces can consume
  Workbench-equivalent Analyze Workspace, Create Project, and Edit Brief
  variants without parsing the compact summary string.
- Added JSON status coverage for complete existing-project intake, incomplete
  new-project brief recovery, missing existing targets, and missing new-project
  target recreation.
- Raised the package version from `1.0.728` to `1.0.729` in this patch PR.

### #828: Project Onboarding Action Labels

- Changed Start/Nexus project-intake action labels from generic workspace
  wording to journey-oriented labels: `Analyze Existing` and `Create New`.
- Updated Korean labels to `기존 프로젝트 분석` and `새 프로젝트 생성` so users
  can distinguish existing-project analysis from new-project creation before
  opening the workspace picker.
- Preserved the underlying action IDs and readiness/variant behavior so
  existing tests and automation can continue using `analyze_workspace` and
  `create_project`.
- Added Start/Nexus label coverage and updated the project-intake workspace
  profile contract.
- Raised the package version from `1.0.730` to `1.0.731` in this patch PR.

### #830: Init New Project Creation Options

- Added `trinity init --project-name NAME` so init can create a new target
  workspace and write `.trinity/project-intake.*` in one setup flow.
- Let `--project-name` imply new-project onboarding when `--mode` is omitted,
  while rejecting the incompatible `--mode existing --project-name` combination
  before creating `.trinity/` or a target folder.
- Reused new-project brief options and intake next-step guidance so incomplete
  briefs still show the completion command after init-created workspaces.
- Preserved the older `trinity init --mode new` deferred behavior when no
  project name is provided.
- Added CLI coverage for deferred mode, init-created new projects, implied new
  mode, and incompatible mode validation.
- Raised the package version from `1.0.732` to `1.0.733` in this patch PR.

### #832: Dirty Workspace Execute Preflight Gate

- Added a dirty-Git safety gate to Execute Preflight. The first
  `Confirm Execute` on a dirty Git workspace now shows a warning and keeps the
  modal open.
- Requires the user to press `Confirm Execute` again on the same path before
  execution continues, making "execute anyway" explicit.
- Kept Select Workspace mode ungated so read-only target selection and analysis
  remain fast.
- Added WorkspacePicker coverage for clean/dirty preflight state, execute mode
  double-confirm behavior, and select-mode bypass behavior.
- Raised the package version from `1.0.734` to `1.0.735` in this patch PR.

### #834: Stale/Sparse Intake Execute Preflight Gate

- Added stale/sparse project-intake safety warnings to Execute Preflight for
  existing-project targets.
- Reused the two-step execute confirmation gate so stale or sparse intake
  requires an explicit second `Confirm Execute` before running.
- Kept Select Workspace mode ungated for read-only target selection and
  analysis.
- Added WorkspacePicker coverage for sparse intake, stale intake, execute-mode
  confirmation, and select-mode bypass behavior.
- Raised the package version from `1.0.736` to `1.0.737` in this patch PR.

### #836: Empty Workspace New-Project Candidate

- Treated existing empty non-Git directories as new-project candidates in the
  Workbench preflight.
- Synced those empty workspace candidates as `new` project intake so users who
  create a folder outside Trinity still get new-project brief readiness and
  prompt guidance.
- Kept non-empty non-Git directories on the existing-project path to avoid
  reclassifying real workspaces.
- Added WorkspacePicker and Textual app coverage for empty directory
  classification and intake mode sync.
- Raised the package version from `1.0.738` to `1.0.739` in this patch PR.

### #838: Provider Target Workspace CWD Regression

- Added a fake-provider regression test that drives a real Codex fake CLI through
  the orchestrator-created agent wrapper.
- Verified that the selected target workspace, not the Trinity control repo, is
  used as the provider subprocess cwd.
- Verified that Codex receives the selected target workspace through its
  controlled `--cd` argument and still receives the expected prompt context on
  stdin.
- Documented this fake-provider coverage in the development test environment.
- Raised the package version from `1.0.740` to `1.0.741` in this patch PR.

### #840: Incomplete New-Project Brief Execute Gate

- Added incomplete new-project brief warnings to Execute Preflight safety
  checks.
- Required a second `Confirm Execute` when a saved new-project intake is missing
  required brief fields or an empty new-project candidate has no saved intake.
- Kept completed new-project briefs ungated and kept Select Workspace mode
  read-only and ungated.
- Added WorkspacePicker coverage for missing brief warnings, complete brief
  bypass, and execute-mode double-confirm behavior.
- Raised the package version from `1.0.742` to `1.0.743` in this patch PR.

### #842: Changed Existing-Project Intake Execute Gate

- Added a read-only live profile comparison for matching existing-project intake
  during Execute Preflight.
- Marked changed Git state, package manager signals, test/dev/build commands,
  entrypoints, source roots, or documentation anchors as `changed_project_intake`.
- Reused the two-step `Confirm Execute` safety gate while keeping Select
  Workspace mode ungated.
- Added project-intake and WorkspacePicker coverage for unchanged intake, changed
  analysis anchors, changed Git state, and execute-mode double-confirm behavior.
- Raised the package version from `1.0.744` to `1.0.745` in this patch PR.

### #844: Project Status Intake Drift

- Extended `trinity project status` so CLI users can see when saved
  existing-project intake differs from the current workspace profile before
  opening the Workbench.
- Added JSON readiness fields `analysis_changed` and
  `analysis_changed_fields`.
- Recommended `trinity project status --refresh` before `trinity` when saved
  existing-project analysis has drifted.
- Added CLI coverage for changed source-root anchors and verified `--refresh`
  clears the drift by rewriting saved intake.
- Raised the package version from `1.0.746` to `1.0.747` in this patch PR.

### #846: Workbench Intake Drift Labels

- Extended Start/Nexus project-intake labels so changed existing-project intake
  is visible before opening Execute Preflight.
- Added a changed-analysis label and reused the `trinity project analyze
  <target>` refresh hint.
- Highlighted the Workbench "Analyze Existing" action when the saved
  existing-project profile differs from the live workspace profile.
- Preserved missing target, target mismatch, sparse analysis, and stale analysis
  priority over changed-analysis hints.
- Added Start screen coverage for English/Korean changed labels and Analyze
  Existing warning variants.
- Raised the package version from `1.0.748` to `1.0.749` in this patch PR.

### #848: Workbench Intake Refresh Action Label

- Changed Start/Nexus analyze action labels to `Refresh Analysis` /
  `분석 갱신` when the selected existing-project intake already matches the active
  workspace but needs refresh because it is sparse, stale, or changed.
- Preserved the existing analyze-workspace action ids and event flow, so the
  button still rebuilds and writes project intake through the existing path.
- Kept `Analyze Existing` / `기존 프로젝트 분석` for missing intake, target
  mismatch, target recovery, and non-refresh cases.
- Added Start/Nexus mounted-screen coverage for dynamic button label refresh and
  sparse/stale/changed label-key cases.
- Raised the package version from `1.0.750` to `1.0.751` in this patch PR.

### #850: Workbench Analyze Action Presentation

- Added a shared Workbench analyze action presentation helper that returns both
  the label key and variant from one project-intake readiness decision.
- Updated Start/Nexus compose and refresh paths to compute the analyze action
  presentation once, then apply both button label and variant from that result.
- Kept the existing public label-key and variant helpers as compatibility
  wrappers around the shared presentation helper.
- Added presentation coverage for normal, sparse, stale, and changed intake
  states.
- Raised the package version from `1.0.752` to `1.0.753` in this patch PR.

### #852: New Project Brief Handoff

- Routed Start `Create New` and Nexus `Create Project` through
  create-specific workspace callbacks.
- Opened the existing project brief modal immediately after a created or empty
  new-project workspace is confirmed.
- Kept normal workspace selection, existing-project analysis, and execute
  preflight behavior unchanged.
- Preserved the Nexus control-repo confirmation guard before opening the brief
  modal.
- Added a dedicated design document and Textual coverage for Start/Nexus create
  flows.
- Raised the package version from `1.0.754` to `1.0.755` in this patch PR.

### #854: Existing Project Analysis Prompt Handoff

- Seeded the Start composer with a localized default analysis prompt after
  `Analyze Existing` writes an existing-project intake.
- Preserved any user-written prompt instead of overwriting it.
- Routed Start picker completions for existing-project analysis through an
  analysis-specific callback so control-repo launches get the same handoff.
- Kept Nexus follow-up composition, normal workspace selection, and execute
  preflight behavior unchanged.
- Added a dedicated design document and Textual coverage for prompt seeding and
  preservation.
- Raised the package version from `1.0.756` to `1.0.757` in this patch PR.

### #856: Project Brief Start Prompt

- Replaced the single-field project brief prompt seed with a concise prompt
  builder that includes goal, type, users, success criteria, first milestone,
  stack, constraints, and notes when present.
- Kept goal-only saved intake compatible by preserving the previous single-line
  prompt behavior.
- Used separate lead-in text for new projects and existing-project briefs.
- Reused the same prompt builder for initial Start composer loading and project
  brief save handling.
- Added a dedicated design document and Textual coverage for initial prompt
  loading, new-project brief save, and existing-project brief save.
- Raised the package version from `1.0.758` to `1.0.759` in this patch PR.

### #858: Nexus Brief Follow-Up Prompt

- Seeded the Nexus follow-up composer from the saved project brief when the
  active route is Nexus and the composer is empty.
- Kept Start prompt seeding unchanged while avoiding stale Nexus prefill from
  Start-only brief edits.
- Preserved user-written Nexus follow-up text instead of overwriting it.
- Reused the shared project-brief prompt builder for Nexus and Start.
- Added a dedicated design document and Textual coverage for Nexus composer
  seed and preservation behavior.
- Raised the package version from `1.0.760` to `1.0.761` in this patch PR.

### #860: Nexus Existing Analysis Follow-Up Prompt

- Seeded the Nexus follow-up composer after `Analyze Existing` writes an
  existing-project intake and the composer is empty.
- Preserved user-written Nexus follow-up text.
- Routed picker-based Nexus analysis through an analysis-specific callback while
  preserving the control-repo confirmation guard.
- Updated stale Nexus button label expectations to match current UI terms:
  `Analyze Existing` and `Create New`.
- Added a dedicated design document and Textual coverage for Nexus analysis
  prompt seed and preservation behavior.
- Raised the package version from `1.0.762` to `1.0.763` in this patch PR.

### #862: Analyze Picker New Brief Handoff

- Routed Start and Nexus `Analyze Existing` picker selections classified as
  new-project candidates into the project brief modal.
- Prevented incomplete `new` intake from being left without an immediate
  recovery step when users select an empty workspace from the analysis picker.
- Kept existing-project picker selections unchanged: write existing intake and
  seed the analysis prompt.
- Left `Select Workspace`, `Create New`, direct brief editing, and execute
  preflight flows unchanged.
- Added a dedicated design document and Textual coverage for Start/Nexus empty
  target picker selections.
- Raised the package version from `1.0.764` to `1.0.765` in this patch PR.

### #864: Direct Analyze New Brief Handoff

- Classified direct Start/Nexus `Analyze Existing` targets with Workspace
  Preflight before writing project intake.
- Routed empty direct targets into `new` intake and the project brief modal
  instead of writing `existing` intake.
- Kept existing direct analysis behavior for workspaces with user files and
  preserved existing prompt seed behavior.
- Added a dedicated design document and Textual coverage for Start/Nexus direct
  empty target flows.
- Raised the package version from `1.0.766` to `1.0.767` in this patch PR.

### #866: New Brief Missing Field Prompt

- Added missing-field guidance to seeded Start/Nexus prompts for incomplete
  new-project briefs.
- Listed empty `project_type`, `target_users`, `success_criteria`, and
  `first_milestone` fields as items to confirm before scaffolding.
- Kept existing-project prompts and complete new-project brief prompts on their
  existing behavior.
- Added a dedicated design document and focused English/Korean Textual prompt
  coverage.
- Raised the package version from `1.0.768` to `1.0.769` in this patch PR.

### #868: Existing Analysis Target Prompt

- Added the selected target workspace path to Start/Nexus `Analyze Existing`
  seed prompts.
- Guided agents to read existing docs, source roots, and test/build signals
  before proposing safe work packages.
- Added explicit safety wording to avoid new-project scaffolding for non-empty
  existing workspaces.
- Added a dedicated design document and Start/Nexus prompt coverage.
- Raised the package version from `1.0.770` to `1.0.771` in this patch PR.

### #870: Project Brief Placeholders

- Added localized placeholder examples to project brief modal inputs.
- Helped first-run new-project users understand the expected detail for goal,
  project type, users, success criteria, stack, milestone, constraints, and
  notes.
- Preserved existing draft values, save behavior, readiness policy, and
  preflight gates.
- Added a dedicated design document and English/Korean Textual modal coverage.
- Raised the package version from `1.0.772` to `1.0.773` in this patch PR.

### #872: New Brief Starter Recommendations

- Added prompt-only starter recommendations for new-project brief prompts.
- Derived advisory template, stack, UX focus, and guardrail hints from saved
  project type, stack preferences, target users, and constraints.
- Kept existing-project prompts, intake persistence, readiness policy, and
  preflight gates unchanged.
- Added a dedicated design document and English/Korean prompt coverage.
- Raised the package version from `1.0.774` to `1.0.775` in this patch PR.

### #874: Project Brief Target Display

- Displayed the selected target workspace path at the top of the project brief
  modal.
- Localized the target label for English and Korean users.
- Kept brief save behavior, intake persistence, readiness policy, and preflight
  gates unchanged.
- Added a dedicated design document and Start/Korean modal coverage.
- Raised the package version from `1.0.776` to `1.0.777` in this patch PR.

### #876: Existing Analysis Read Preview

- Added a localized `read first` / `먼저 읽기` preview to existing-project
  intake labels when docs or source roots are detected.
- Derived the preview from saved `docs_found` and `source_roots` without
  changing intake persistence or detection.
- Kept new-project labels, detailed profile sections, readiness policy,
  prompts, and preflight gates unchanged.
- Added a dedicated design document and Start label coverage for English,
  Korean, sparse existing, and new-project cases.
- Raised the package version from `1.0.778` to `1.0.779` in this patch PR.

### #878: Project Brief Cancel Draft Cache

- Preserved canceled project brief edits in memory for the current Workbench
  session.
- Restored canceled drafts when reopening the brief for the same target
  workspace.
- Cleared cached drafts on Save and kept saved project intake as the durable
  source of truth.
- Avoided persisting canceled drafts to disk and left intake JSON, readiness,
  preflight, and provider prompt contracts unchanged.
- Added a dedicated design document and Textual coverage for cancel, reopen,
  save, and target isolation behavior.
- Raised the package version from `1.0.780` to `1.0.781` in this patch PR.

### #879-#889: Project Intake Preview Expansion

- Added target-aware existing analysis prompts, anchor review, scope previews,
  starter profiles, generation previews, validation previews, and read-first
  checklists.
- Continued improving new-project and existing-project intake context before
  the later Workbench simplification pass.

### #890-#940: Project Safety Gates and Runtime Feedback

- Added provider execution/review policy, handoff context, launch CWD priority,
  target mismatch recovery, generation conflict previews, execute
  acknowledgement, self-check review, read-first evidence, execution risk gates,
  and run estimates.
- Expanded project confirmation, scope, validation, starter preset, dry-run,
  and diagnostic flows before those controls were later consolidated.

### #941-#954: Start/Nexus Density and Provider Notice Cleanup

- Shifted project command output toward diagnostics.
- Tightened workspace labels, provider inspector copy, recipient controls, and
  Start geometry for narrower terminals.
- Began moving provider notices out of persistent screen chrome.

### #955-#976: Narrow Viewport and Render Cost Hardening

- Added narrow-layout coverage for Nexus, command/modals, project confirmation
  dialogs, model settings, work package detail, execution logs, and retry
  modals.
- Reduced repeated execution matrix row/action/log reconciliation work.

### #977-#1081: Prompt-Led Workbench Simplification

- Simplified the Nexus action bar and Start workspace action.
- Added provider inspector and workspace slash commands.
- Made `/project` diagnostics-only and removed workbench project setup slash
  shortcuts, modal runtime paths, and unused project setup widgets.
- Replaced button-led readiness with prompt-led `workbench_next_step` metadata.
- Removed stale project CTA/selector tests, superseded Workbench action notes,
  old Workbench plan reports, obsolete init next-step wording, stale
  `project_start_guide` assertions, dead project rail/runtime notes,
  superseded readiness notes, unused auto-seed prompt helpers, and the leftover
  unused `absolute_path` import.
- Removed the old new/existing onboarding redesign plan that still described
  mode-led Workbench surfaces after the prompt-led contract replaced them.
- Removed the leftover `initial_start_prompt` helper and its stale intake
  regression test now that Start always begins from a blank user prompt.
- Removed the unused `config` parameter and stale intake setup from
  `initial_workspace_candidate` tests while preserving launch-cwd defaulting.
- Removed the stale Nexus project-intake summary offscreen test after the
  summary widget was removed from the prompt-led Workbench surface.
- Moved Nexus refine action prompt text into a pure presenter helper so
  `NexusScreen` only routes the action.
- Moved provider-error central action answer mapping into the provider error
  gate contract and removed the duplicate Nexus private helper.
- Moved Nexus current-workspace text resolution into a pure presenter helper and
  removed the screen private method from tests.
- Inlined one-use Nexus provider strip setup helpers in `compose()`.
- Moved Nexus central activity-frame eligibility into a pure presenter helper.
- Moved provider snapshot to provider panel state mapping into a presenter
  helper and removed the Nexus private static method.
- Moved config agent to provider panel state mapping into the same presenter
  layer and removed the remaining Nexus private mapping helper.
- Moved Nexus fallback snapshot construction into a pure presenter helper.
- Exposed provider panel state grouping as a public helper and removed Nexus'
  dependency on the widget private method.
- Exposed provider panel CSS class generation as a public helper and removed
  the remaining provider panel private helper dependency from tests.
- Exposed provider inspector output formatting/selection helpers and removed
  direct test dependency on the inspector private output method.
- Exposed provider panel status label rendering as a public helper and removed
  the widget private status label method.
- Exposed provider panel summary rendering as a public helper and removed the
  widget private summary method.
- Exposed provider panel metadata line rendering as a public helper and
  removed the widget private provider-line helper chain.
- Exposed CentralAgentView markdown rendering through a public method and
  removed direct test dependency on its private markdown method.
- Exposed CentralAgentView blueprint action rendering through a public method
  and removed direct test dependency on its private action renderer.
- Exposed CentralAgentView label lookup through a public method and removed
  direct test dependency on its private label method.
- Exposed CentralAgentView execution progress rendering through a public method
  and removed direct test dependency on its private execution progress method.
- Exposed CentralAgentView local command table rendering through a public
  method and removed direct test dependency on its private table renderer.
- Exposed NexusScreen workspace label rendering through a public method and
  removed direct test dependency on its private workspace label helper.
- Exposed SettingsScreen preview rendering through a public method and removed
  direct test dependency on its private preview helper.
- Exposed ModelSettingsModal choice label rendering through a public method
  and removed direct test dependency on its private choice label helper.
- Exposed ExecutionMatrixScreen activity line rendering through a public method
  and removed direct test dependency on its private activity log helper.
- Exposed WorkPackageDetailModal markdown rendering through a public method
  and removed direct test dependency on its private markdown helper.
- Exposed ExecutionLogModal line and status rendering through public methods
  and removed direct test dependency on its private log rendering helpers.
- Exposed StatusCommandModal status table rendering through a public method
  and removed direct test dependency on its private status table helper.
- Exposed ExecutionRetryModal summary, header, and selected text rendering
  through public methods and removed direct test dependency on private text helpers.
- Exposed WorkPackageDetailModal title rendering through a public method and
  removed direct test dependency on its private title helper.
- Exposed ExecutionRetryModal displayed package and selected package id
  resolution through public methods and removed direct test dependency on
  private retry selection helpers.
- Exposed ExecutionRetryModal retry filter label and selector id resolution
  through public methods and removed direct test dependency on private filter
  helpers.
- Exposed ExecutionConfirmModal summary text rendering through a public method
  and removed direct test dependency on its private summary helper.
- Exposed StatusCommandModal chrome label lookup through a public method and
  removed direct test dependency on its private label helper.
- Exposed ContextCommandModal chrome label lookup through a public method and
  removed direct test dependency on its private label helper.
- Exposed LocalCommandModal chrome label lookup through a public method and
  removed direct test dependency on its private label helper.
- Exposed ExecutionRetryModal chrome label lookup through a public method and
  removed direct test dependency on its private label helper.
- Exposed SharedContextEngine markdown heading sanitization through a public
  method and removed direct test dependency on its private sanitizer helper.
- Exposed ExecutionMatrixScreen package list lookup through a public method and
  removed direct test dependency on its private widget accessor.
- Exposed ExecutionMatrixScreen task-expanded class synchronization through a
  public method and removed direct test dependency on its private sync helper.
- Exposed WorkspaceIsolation branch name generation through a public method and
  removed direct test dependency on its private branch helper.
- Exposed WorkspaceIsolation worktree path resolution through a public method
  and removed direct test dependency on its private path helper.
- Exposed WorkflowReviewFlow latest review approval lookup through a public
  method and removed direct test dependency on its private approval helper.
- Exposed WorkflowEngine latest review approval facade and removed direct test
  dependency on its private review-flow accessor.
- Exposed StartScreen and NexusScreen label lookup through public methods and
  removed direct test dependency on their private label helpers.
- Centralized StartScreen and NexusScreen prompt/warning labels in the shared
  Textual UI text table.
- Replaced the remaining ProviderInspector and SettingsScreen chrome label
  tests with public label helpers.
- Reduced Start/Nexus recipient selector visual weight by shortening the Korean
  label and removing always-on toggle backgrounds.
- Removed the unused new-project generation confirmation modal and its dry-run
  label helpers after the prompt-led flow made that UI path obsolete.
- Renamed Textual execution confirmation context from `project_mode` to
  `workspace_context` so the confirm path no longer carries mode-led wording.
- Neutralized recorded workspace context labels so execution confirmation does
  not distinguish new/existing intake modes in its top-level context line.
- Removed obsolete new-project generation confirmation and dry-run development
  notes after that modal path was deleted.
- Aligned new-project plan/generation preview notes with the current prompt-led
  flow: previews remain in `/project` diagnostics and CLI status instead of
  always-visible Start/Nexus chrome.

This refresh moves the project further from "large batch of one-PR plans" to a
smaller set of durable maintenance documents and focused archive bundles. Root
`docs/plans/` no longer contains the deleted 2026-06-05 Workbench plan/report
set or the 2026-06-27 one-PR plans. Older architecture and migration plans
remain in the root; archive only the groups that have a current contract
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
- `docs/development/project-intake-workspace-profile.md`

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

Current main snapshot after #1073:

- `src/trinity/textual_app/app.py`: 3,447 lines
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
