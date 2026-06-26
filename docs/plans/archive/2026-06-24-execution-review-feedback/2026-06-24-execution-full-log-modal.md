# Execution Full Log Modal

## Problem

The execution page currently uses the activity toggle to render every execution
log line inline. Long workflow logs can make the execution page heavier exactly
when users need the package matrix to stay responsive.

## Design

- Keep the execution page activity area as a recent feed.
- Open the full execution log in a modal from the existing `Full Log` button and
  `l` binding.
- Reuse the same log source order as the activity feed:
  - `execution_log` first.
  - `workflow_events` fallback.
- Localize modal title, empty state, and close action for Korean UI mode.

## Acceptance

- The execution page no longer expands the inline activity feed to all log lines.
- `Full Log` opens a modal containing the complete execution log.
- The recent activity feed still caps the visible lines.
- Existing package matrix rendering and retry behavior remain unchanged.
