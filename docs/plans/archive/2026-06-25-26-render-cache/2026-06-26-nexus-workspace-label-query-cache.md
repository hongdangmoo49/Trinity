# Nexus Workspace Label Query Cache

## Context

`NexusScreen._refresh_workspace_label()` already skips `Static.update()` when
the visible workspace label has not changed. The method still queries
`#nexus-target-workspace` before comparing the new label with
`_workspace_label_key`.

This path runs during Nexus snapshot application and workspace candidate
updates. If the label is unchanged, the screen can return before touching the
widget tree.

## Goal

Skip workspace label widget lookup when the rendered label text is unchanged.

## Design

- Compute `_workspace_label()` first.
- Compare it with `_workspace_label_key`.
- Return immediately on unchanged text.
- Only query `#nexus-target-workspace` and call `Static.update()` when the label
  changed.

## Tests

- Extend the Nexus workspace label cache test.
- Verify repeated `_refresh_workspace_label()` calls with the same label do not
  query `#nexus-target-workspace`.
- Keep the existing changed-workspace update assertion.

## Versioning

Patch release: `1.0.256` -> `1.0.257`.
