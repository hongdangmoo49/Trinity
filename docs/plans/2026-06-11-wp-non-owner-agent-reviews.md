# WP Non-Owner Agent Reviews

Date: 2026-06-11

Branch: `feature/wp-non-owner-agent-reviews`

Status: implementation in progress

## Goal

When a work package finishes execution, every active agent that did not perform
that package should review it. A WP owned or executed by `codex` with active
agents `claude`, `codex`, and `antigravity` should therefore create two review
tasks:

- `claude` reviews the `codex` work.
- `antigravity` reviews the `codex` work.

The owner/executor should not review its own WP unless it is the only active
agent available.

## Current Behavior

`PeerReviewPlanner.plan_reviews()` previously chose one reviewer per WP by
rotating through non-owner candidates. This gave coverage, but not full
cross-agent review. For example, a `codex` WP might be reviewed by `claude`,
while `antigravity` would not review that same WP.

`ReviewExecutionProtocol.review_work_packages()` already accepts a list of
review packages and runs each package review. The main missing piece is the
planner policy and the engine filter for pending review requests.

## Design

### Review Package Planning

For each reviewable WP:

1. Resolve the target agent from `ExecutionResult.agent_name` when available.
2. Otherwise use `WorkPackage.owner_agent`.
3. Build reviewers from all active agents except the target agent.
4. If that list is empty, create one self-review package for the target agent.

This keeps single-agent sessions usable while making multi-agent sessions use
all available peer reviewers.

### Pending Review Filtering

Review requests must operate at review-package granularity, not just WP
granularity. If one reviewer approves a WP but another reviewer has not run yet,
`/review wp` should still return the remaining reviewer task.

The engine now treats a WP as fully approved only when every planned non-final
review package for that WP has an approved result. Individual review packages
that already have an approved result are skipped from the default pending list.

### Existing Review Execution

No major execution-protocol rewrite is needed. The review protocol already runs
all selected review packages and emits per-review events. The change increases
the number of review packages passed into that existing path.

## Validation Plan

- Unit test the planner output for all non-owner reviewers.
- Unit test engine planning after execution completion.
- Unit test pending review filtering after one reviewer approves.
- Run peer review, workflow engine, review execution, Textual controller, and
  plain TUI review tests.

## Expected UX

After WP execution completes, the review phase may show more review tasks than
before. This is intentional: every non-owner active agent reviews each completed
WP. If any reviewer requests changes, the existing review-repair loop should
send the WP back to the actual executor for follow-up.
