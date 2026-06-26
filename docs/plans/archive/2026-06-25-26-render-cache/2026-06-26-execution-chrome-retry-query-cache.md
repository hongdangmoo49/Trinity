# Execution Chrome Retry Query Cache

## Context

`ExecutionMatrixScreen._render_chrome()` already keeps a render key for the
execution header, summary, task toggle, activity toggle, and retry button state.
When the render key changes because only the header or summary changed, the
method still queries `#execution-retry` before checking whether the retry label
or disabled state changed.

This is small, but it sits on the execution page's live refresh path. The
screen should avoid widget tree lookups when the target widget cannot change.

## Goal

Only query the retry button when its label or disabled state actually changes.

## Design

- Compute `retry_label_changed` and `retry_disabled_changed` from the previous
  chrome projection.
- Query `#execution-retry` only when either value changed.
- Keep the existing full render-key guard, header/summary update guards, and
  toggle label guards intact.

## Tests

- Extend the execution chrome summary-change test.
- Verify summary-only changes update the summary text but do not query the retry
  button.

## Versioning

Patch release: `1.0.255` -> `1.0.256`.
