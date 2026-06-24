# Nexus Provider Error Status

## Problem

Nexus provider panels can display a provider as completed when the visible
summary is an explicit provider failure such as `[Error: exit code 1]`. This is
confusing because the status badge communicates success while the body says the
provider failed.

## Design

- Treat explicit provider error snippets as issue state even when older event
  producers omit `response_status`.
- Keep the existing `response_status != ok` path as the primary signal.
- Use a conservative text fallback for common wrapper output:
  - `[Error: ...]`
  - `Error: ...`
  - `Traceback ...`
  - `exit code ...`
- Do not change successful `Ready` / `Done` rendering.

## Acceptance

- A provider panel with summary `[Error: exit code 1]` renders the issue status.
- Korean labels show `문제` rather than `완료` for that panel.
- Existing provider status labels continue to pass.
