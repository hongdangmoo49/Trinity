# Completed Plan Index

This index maps completed one-PR plan files to the larger work bundles described
in `docs/development/ci-and-maintenance-strategy.md`. Use it before archiving
or deleting old implementation plans.

## Scope

- Reviewed baseline: PR #90 through #540
- Current index focus: completed one-PR plans from the Nexus/workflow/Textual
  cleanup runs, especially the dense 2026-06-25 through 2026-06-27 files.
- This is not an active roadmap. Active roadmap items belong in
  `docs/development/ci-and-maintenance-strategy.md`.

## Bundle Map

| Bundle | PR range | Plan files | Archive readiness |
| --- | --- | --- | --- |
| Fake provider and facade baseline | #90-#96 | fake provider harness and early facade notes | Fake provider CI smoke plan archived after harness and E2E coverage |
| Nexus projection and performance budgets | #97-#108 | snapshot, event-tail, and performance-budget plans | Keep as performance baseline |
| Execution UX and retry/review feedback | #109-#160 | execution, retry, review, provider metadata, report metadata plans | 2026-06-24 execution/review feedback plans archived after Nexus state contract |
| Korean UX vocabulary stabilization | #161-#292 | 2026-06-24/25 `*i18n*`, `*-ko`, `*korean*`, status, placeholder, and term plans | Explicit i18n/ko/korean and 2026-06-25 UI label/status plans archived |
| Nexus/Textual render cost reduction | #293-#391 | 2026-06-25 and 2026-06-26 cache/rebind/query plans | Explicit render cache/rebind/query plans archived after performance guidance |
| Workflow flow decomposition | #392-#409 | 2026-06-26 `workflow-*`, `provider-*`, review/post-review flow plans | Keep as architecture trace; flow and provider readiness/recovery contract docs exist |
| Textual presenter and wrapper removal | #410-#426 | 2026-06-26 `textual-*`, command parser, facade-thin plans | Ready for bundle archive after presenter contract docs exist |
| CI maintenance strategy | #427 | `README.md`, this index, CI strategy doc | Active maintenance reference |
| Textual helper continuation | #488-#492, #518-#532 | 2026-06-27 Textual command, route, workspace, and recovery helper plans | Archived after maintenance strategy #540 refresh and required smoke coverage |
| Workflow facade cleanup | #493-#517 | 2026-06-27 workflow wrapper removal, persistence, and flow contract plans | Archived after maintenance strategy #540 refresh and workflow flow contract coverage |
| Post-review maintenance helpers | #534-#537 | 2026-06-27 post-review helper extraction plans | Archived after helper modules and post-review smoke coverage landed |
| Maintenance followups | #486, #533, #538-#545 | 2026-06-27 target helper, Nexus event render, smoke runner, review repair metadata, CI fast path, and archive closure plans | Archived after all 2026-06-27 root follow-up plans had merged PR and required smoke evidence |

## Workflow Flow Decomposition Plans

These plans describe completed flow extraction work and should be kept until
`WorkflowEngine` facade boundaries are stable for a minor release.

- `2026-06-26-provider-error-gate-flow-refactor.md`
- `2026-06-26-orchestrator-readiness-runtime-v2.md`
- `2026-06-26-workflow-execution-flow-module.md`
- `2026-06-26-workflow-review-flow-module.md`
- `2026-06-26-workflow-post-review-flow-module.md`
- `2026-06-26-post-review-flow-helpers.md`
- `2026-06-26-review-repair-flow-helpers.md`
- `2026-06-26-review-package-planning-flow.md`
- `2026-06-26-workflow-ledger-sync.md`
- `2026-06-26-workflow-central-interaction.md`
- `2026-06-26-workflow-provider-observations.md`
- `2026-06-26-workflow-question-flow.md`
- `2026-06-26-workflow-input-routing.md`
- `2026-06-26-workflow-lifecycle-flow.md`
- `2026-06-26-workflow-workspace-flow.md`
- `2026-06-26-workflow-quality-flow.md`
- `2026-06-26-workflow-targeting-flow.md`
- `2026-06-26-workflow-collection-flow.md`

## Workflow Facade Cleanup Plans

These plans are completed wrapper removal and persistence-flow cleanup slices
from #493-#517. Their durable boundary is summarized in
`docs/development/workflow-flow-contracts.md` and the current maintenance
strategy, while behavior remains covered by the workflow flow tests and
required smoke suite.

Archived bundle:

- `docs/plans/archive/2026-06-27-workflow-facade-cleanup/`

The archived bundle contains the #493-#517 plans for review, result
collection, post-review, work-package lookup, execution-run, review-repair
metadata, unused-result, execution-support, quality, provider-observation,
execution-intent, lifecycle/question, central-prompt, ledger-parser, targeting,
persistence, direct persistence, decomposition-agent, engine-persist, and flow
contract cleanup.

## Fake Provider Baseline Plans

The original fake-provider CI smoke plan is now archived because the durable
testing contract lives in `docs/development/fake-provider-test-environment.md`
and the required smoke list includes both fake-provider harness and E2E tests.

Archived bundle:

- `docs/plans/archive/2026-06-24-fake-provider-baseline/`

## Textual Presenter and Facade Plans

These plans are mostly completed mechanical extractions. Their active contract
is now summarized in `docs/development/textual-presenter-parser-contract.md`, so
future archive work can move these one-PR notes by bundle after checking tests.

Archived bundle:

- `docs/plans/archive/2026-06-26-textual-presenters/`

- `archive/2026-06-26-textual-presenters/2026-06-26-textual-agent-presenter.md`
- `archive/2026-06-26-textual-presenters/2026-06-26-textual-local-command-presenter.md`
- `archive/2026-06-26-textual-presenters/2026-06-26-textual-ask-command-parser.md`
- `archive/2026-06-26-textual-presenters/2026-06-26-textual-status-history-presenters.md`
- `archive/2026-06-26-textual-presenters/2026-06-26-textual-workflow-detail-presenters.md`
- `archive/2026-06-26-textual-presenters/2026-06-26-textual-command-help-presenters.md`
- `archive/2026-06-26-textual-presenters/2026-06-26-textual-context-review-presenters.md`
- `archive/2026-06-26-textual-presenters/2026-06-26-textual-session-agent-presenters.md`
- `archive/2026-06-26-textual-presenters/2026-06-26-textual-resume-presenters.md`
- `archive/2026-06-26-textual-presenters/2026-06-26-textual-recovery-presenters.md`
- `archive/2026-06-26-textual-presenters/2026-06-26-execute-retry-command-parser.md`
- `archive/2026-06-26-textual-presenters/2026-06-26-textual-workflow-outcome-presenter.md`
- `archive/2026-06-26-textual-presenters/2026-06-26-textual-local-command-snapshot.md`
- `archive/2026-06-26-textual-presenters/2026-06-26-textual-ask-parser-direct.md`
- `archive/2026-06-26-textual-presenters/2026-06-26-workflow-recovery-facade-thin.md`
- `archive/2026-06-26-textual-presenters/2026-06-26-provider-error-gate-flow-reuse.md`
- `archive/2026-06-26-textual-presenters/2026-06-26-workflow-execution-facade-thin.md`

## Textual Helper Continuation Plans

These plans are completed helper extraction slices from the 2026-06-27 Textual
cleanup pass. Their active behavior is covered by Textual command, runtime,
workflow controller, target workspace, and TUI rendering tests in the required
smoke suite.

Archived bundle:

- `docs/plans/archive/2026-06-27-textual-helper-continuation/`

The archived bundle contains the #488-#492 and #518-#532 plans for command
result helpers, local command presentation, execution recovery and review
repair presentation, route snapshot application, report route preparation,
snapshot source handling, launch cwd handling, target workspace helpers,
workspace picker/candidate/apply helpers, and execution state extraction.

## Post-Review Maintenance Helper Plans

These plans are completed helper extraction slices from the post-review
maintenance pass. Their active behavior is covered by the post-review flow
module and the required smoke suite, so the one-PR implementation notes are
archived as a dated bundle.

Archived bundle:

- `docs/plans/archive/2026-06-27-post-review-maintenance/`

The archived bundle contains the #534-#537 plans for post-review item
selection, owner assignment, supplemental WorkPackage construction, and
supplemental execution run payload construction.

## Maintenance Followup Plans

These plans are completed follow-up slices from the 2026-06-27 maintenance pass.
Their active behavior is covered by dedicated helper tests, snapshot/performance
tests, required smoke runner tests, and the required smoke suite.

Archived bundle:

- `docs/plans/archive/2026-06-27-maintenance-followups/`

The archived bundle contains the #486, #533, #538-#545, and related Textual
target helper plans for review repair metadata, Nexus workflow event render limits,
required smoke runner manifest validation, CI fast path classification,
maintenance strategy refresh, and the completed archive closure PRs.

## Render Cost Reduction Plans

These plans are completed performance slices. Their active cache guidance is
summarized in `docs/development/nexus-render-cache-guidelines.md`, so future
archive work can move the individual one-PR notes by date.

Archived bundle:

- `docs/plans/archive/2026-06-25-26-render-cache/`

The archived bundle contains the explicit cache, rebind, query, normalization,
delta-apply, field-update, single-pass, recent-slice, filter-once, and
prefix-append one-PR plans from 2026-06-25 and 2026-06-26. Non-cache UX,
architecture, and runtime-flow plans remain in the root until their contracts
are documented separately.

- 2026-06-25 cache and identity plans:
  `execution-*`, `nexus-*`, `provider-*`, `question-*`, `report-*`,
  `model-*`, `start-*`, `workspace-*`, `central-*`, and `prompt-*`.
- 2026-06-26 cache and rebind plans:
  `*-widget-cache.md`, `*-render-key-rebind.md`, `*-cache-rebind.md`,
  `*-query-cache.md`, `*-status-key-normalization.md`.

Representative files:

- `2026-06-26-execution-log-append-cache-reconcile.md`
- `2026-06-26-nexus-screen-render-cache-rebind.md`
- `2026-06-26-workflow-inspector-render-key-rebind.md`
- `2026-06-26-prompt-composer-render-key-rebind.md`
- `2026-06-26-workspace-picker-status-key-rebind.md`

## Execution And Review Feedback Plans

These plans are completed execution, retry, peer-review, and work-package detail
feedback slices. Their active Nexus projection contract is summarized in
`docs/development/nexus-execution-review-state-contracts.md`.

Archived bundle:

- `docs/plans/archive/2026-06-24-execution-review-feedback/`

The archived bundle contains the 2026-06-24 execution/retry/review feedback
plans that now map to the Nexus execution/review state contract. Older broad
execution redesign documents remain in the root until their migration context is
summarized separately.

## Korean UX Stabilization Plans

These plans are completed terminology and label refinements. Their active
terminology is summarized in `docs/development/korean-ui-glossary.md`, so future
archive work can move these one-PR notes by bundle after checking label tests.

Archived bundle:

- `docs/plans/archive/2026-06-24-25-korean-ux/`
- `docs/plans/archive/2026-06-25-ui-label-status/`

The archived bundle contains the explicit `*i18n*`, `*-ko`, and `*korean*`
one-PR plans from 2026-06-24 and 2026-06-25. Generic `label`, `status`, and
placeholder plans from 2026-06-25 are archived separately after cache and
presenter cleanup plans were split out. Older 2026-06-17 and 2026-06-24
execution/retry status documents remain in the root until the execution UX
contract is documented.

Primary groups:

- command labels: `*-command-i18n.md`, `*-command-title-ko.md`
- state labels: `*-status-labels.md`, `*-status-ko.md`
- workspace terms: `workspace-*`, `target-workspace-*`
- review/retry terms: `review-*`, `retry-*`, `no-peer-review-*`
- report terms: `report-*`
- provider/profile/model terms: `provider-*`, `profile-*`, `model-*`

## Archive Checklist

Before moving a completed plan out of the root:

1. Confirm the PR is merged.
2. Confirm the behavior is covered by focused tests or required smoke tests.
3. Confirm a durable bundle summary exists.
4. Move files by bundle/date, not one-by-one during unrelated feature work.
5. Keep architecture and migration plans in the root until their contracts are
   documented elsewhere.
