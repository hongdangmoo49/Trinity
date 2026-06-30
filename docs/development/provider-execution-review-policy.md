# Provider Execution/Review Policy Label

## Context

Trinity can run with one, two, or three configured providers. The Nexus flow is
designed around parallel provider execution and peer review, but diagnostics
need to explain degraded review expectations when the user selects zero or one
provider.

This is especially confusing for first-run users:

- With one provider, peer review is not available and the user should expect
  self-check/manual review.
- With two providers, one provider can execute while the other reviews.
- With three providers, Trinity can present a larger peer-review pool, but both
  non-owner providers do not need to review every work package.

## Goal

Keep a small, derived policy notice for limited provider coverage so users can
see when execution or peer review is unavailable before submitting work.

## Scope

- Derive the policy from the enabled provider config and the current recipient
  selector state.
- Show the notice only when active provider coverage is limited.
- Keep the label advisory and deterministic.
- Cover zero and one active provider; two or more active providers return no
  notice.

## Non-goals

- Do not change provider routing.
- Do not change work package ownership.
- Do not change the review gate or retry behavior.
- Do not add provider health checks in this PR.

## Policy Copy

The notice should stay compact because it appears in dense diagnostic surfaces.

- `0 active`: execution unavailable, review unavailable.
- `1 active`: single executor, self-check/manual review.
- `2+ active`: no limited-coverage notice.

If the user has selected a subset of enabled providers, the selected subset is
the source of truth for the label. Otherwise, all enabled providers are used.

## Test Plan

- Unit test the label helper for zero, one, two, and three active providers.
- Unit test that selected-agent subsets override the enabled-provider count.
- Verify two-or-more active providers return an empty notice.
