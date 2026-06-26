# Workflow Inspector Section Cache

## Context

`WorkflowInspector` is mounted in the Nexus screen and receives workflow
snapshots together with the central agent and question panel. It already keeps a
snapshot render key and per-section text keys, so unchanged snapshots and
unchanged section text are skipped. When a section does need to change,
`_update_section()` still resolves the fixed section `Static` with
`query_one()`.

The inspector has a stable set of read-only sections, so those widgets can be
cached once during compose.

## Goal

Avoid repeated selector lookups for fixed workflow inspector sections.

## Design

- Cache each section `Static` by selector when the inspector is composed.
- Route `_update_section()` through a section cache helper with a query
  fallback.
- Reset the section widget cache before compose so future recomposition cannot
  retain stale widget references.
- Preserve the existing snapshot render key and section text equality checks.

## Tests

- Add a focused test that verifies changed inspector sections reuse composed
  section widgets without selector lookup.
- Keep the existing unchanged projection test intact.

## Versioning

Patch release: `1.0.276` -> `1.0.277`.
