# Single Provider Self-Check Review

## Context

The Start/Nexus provider policy label says a single active provider uses
single-executor mode with self-check/manual review. The actual review planner,
however, currently creates a non-required skipped review package when no
non-owner peer reviewer is available.

That means single-provider workflows can move past work-package review without a
structured self-check request, even though the UI says self-check is the expected
review mode.

## Goal

Align single-provider review routing with the UI policy by creating a required
self-check review package when no peer reviewer is active.

## Scope

- Keep two-provider and three-provider peer review routing unchanged.
- For one active provider, create a `ReviewDepth.SELF_CHECK` review package.
- Use the executing/owning agent as both reviewer and target.
- Mark the self-check review as required so existing review request flow handles
  it.
- Update peer-review and workflow-engine tests.

## Non-goals

- Do not add a second peer review by default.
- Do not change escalation behavior.
- Do not change review execution prompts.
- Do not add manual user approval gates in this PR.

## Expected Behavior

- One active provider: one required self-check review package.
- Two active providers: one required non-owner peer review package.
- Three active providers: one required non-owner peer review package, with
  escalation remaining optional for high risk or failed primary review.

## Test Plan

- Unit test `PeerReviewPlanner` returns `SELF_CHECK` for one provider.
- Unit test workflow-engine review request includes the self-check package.
- Run required smoke tests before version bump and PR.
