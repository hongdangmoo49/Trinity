# Execution Run Estimate

Date: 2026-06-29
Branch: `feature/execution-run-estimate`

## Problem

Nexus execution confirmation shows target, context, providers, packages, and
risks. It still does not tell users how many agent calls the execution is likely
to trigger.

Users may worry that all providers will review every work package, or may not
notice that a single-provider setup cannot perform peer review.

## Goal

Show a small, conservative agent-run estimate before execution starts.

## User Experience

1. User clicks Execute from Nexus.
2. The confirmation modal shows an `Agent runs` line.
3. The line separates execution and review estimates:
   - one execution run per executable work package
   - one peer-review run per executable work package when at least two providers
     are active
   - zero peer-review runs when only one provider is active

## Implementation Plan

- Extend `ExecutionConfirmationSummary` with execution/review run counts.
- Derive the counts from executable package count and provider count.
- Localize the modal line in English and Korean.
- Add tests for single-provider and peer-review estimates.

## Non-Goals

- Do not estimate token cost or currency.
- Do not change execution or review scheduling.
- Do not make provider-specific pricing assumptions.

## Success Criteria

- Execution confirmation shows approximate execution/review run counts.
- Single-provider summaries show zero peer-review runs.
- Multi-provider summaries show one review run per executable work package.
- Tests and required smoke pass.
