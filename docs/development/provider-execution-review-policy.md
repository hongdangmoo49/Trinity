# Provider Execution/Review Policy Label

## Context

Trinity can run with one, two, or three configured providers. The Nexus flow is
designed around parallel provider execution and peer review, but the UI does not
currently explain how review expectations change when the user enables only one
or two providers.

This is especially confusing for first-run users:

- With one provider, peer review is not available and the user should expect
  self-check/manual review.
- With two providers, one provider can execute while the other reviews.
- With three providers, Trinity can present a larger peer-review pool, but both
  non-owner providers do not need to review every work package.

## Goal

Add a small, derived policy label to Start and Nexus so users can see the active
provider count and the expected execution/review mode before submitting work.

## Scope

- Derive the policy from the enabled provider config and the current recipient
  selector state.
- Show the label on Start and Nexus near the project/workspace guidance labels.
- Keep the label advisory and deterministic.
- Cover zero, one, two, and three-or-more active providers.

## Non-goals

- Do not change provider routing.
- Do not change work package ownership.
- Do not change the review gate or retry behavior.
- Do not add provider health checks in this PR.

## Policy Copy

The label should stay compact because it lives inside a dense TUI surface.

- `0 active`: execution unavailable, review unavailable.
- `1 active`: single executor, self-check/manual review.
- `2 active`: parallel capable, one peer reviewer.
- `3+ active`: parallel capable, peer reviewer pool.

If the user has selected a subset of enabled providers, the selected subset is
the source of truth for the label. Otherwise, all enabled providers are used.

## Test Plan

- Unit test the label helper for zero, one, two, and three active providers.
- Unit test that selected-agent subsets override the enabled-provider count.
- Mount Start and Nexus screens and verify the policy label is rendered.
