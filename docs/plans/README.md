# Plans Directory Guide

`docs/plans/` contains design notes, implementation plans, and one-PR work logs.
Do not treat every file here as active work.

## How To Read This Directory

Start with the durable maintenance summary:

- `docs/development/ci-and-maintenance-strategy.md`
- `docs/plans/completed-index.md`

Then use individual plan files only when you need the detailed reasoning behind
a specific PR or feature area.

Archived one-PR plans are grouped under `docs/plans/archive/`.

## Recent Bundle Map

| PR range | Bundle |
| --- | --- |
| #90-#96 | fake provider harness and facade baseline |
| #97-#108 | Nexus projection limits and performance budgets |
| #109-#160 | Execution UX, retry, review, and report feedback |
| #161-#292 | Korean UX and status vocabulary stabilization |
| #293-#391 | Nexus/Textual render cost reduction |
| #392-#409 | Workflow flow decomposition |
| #410-#426 | Textual presenter/parser wrapper removal and facade thinning |
| #488-#492 | Textual command helper continuation |
| #518-#532 | Textual route, workspace, and recovery helper continuation |
| #534-#537 | Post-review maintenance helper extraction |

## Active vs Historical Plans

Keep a plan file in the root of this directory when it is one of these:

- It describes active or upcoming work.
- It defines a public behavior or migration contract.
- It is the only detailed record for a major architecture decision.

Archive or summarize a plan file when it is one of these:

- It describes a completed one-PR mechanical refactor.
- It only repeats the final implementation already covered by tests and code.
- It is superseded by a durable document in `docs/development/`.

Current archived bundles:

- `archive/2026-06-24-fake-provider-baseline/`
- `archive/2026-06-24-25-korean-ux/`
- `archive/2026-06-24-execution-review-feedback/`
- `archive/2026-06-25-26-render-cache/`
- `archive/2026-06-25-ui-label-status/`
- `archive/2026-06-26-textual-presenters/`
- `archive/2026-06-27-textual-helper-continuation/`
- `archive/2026-06-27-post-review-maintenance/`

## Cleanup Policy

Do not mass-delete plans. Use this order instead:

1. Create or update a durable summary document for the bundle.
2. Confirm the referenced PRs are merged and the behavior is covered by tests.
3. Move historical one-PR plans into a dated archive or replace them with an
   index entry.
4. Keep large architecture plans until their decisions are represented in
   current docs or code comments.

This keeps the project navigable without losing the reasoning behind the long
Nexus/workflow iteration.
