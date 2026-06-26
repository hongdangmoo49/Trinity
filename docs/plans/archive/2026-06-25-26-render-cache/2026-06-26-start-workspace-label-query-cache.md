# Start Workspace Label Query Cache

## Context

`StartScreen.set_workspace_candidate()` skips work when the candidate path object
is unchanged. When the candidate object changes, it currently queries
`#workspace-candidate` before comparing the rendered label with
`_workspace_label_key`.

Nexus now computes the label first and only queries the widget tree when the
visible text changed. Start should follow the same pattern.

## Goal

Skip Start screen workspace label widget lookup when the rendered label text is
unchanged.

## Design

- Store the new candidate path first, as before.
- Compute `_workspace_label()` before querying `#workspace-candidate`.
- Return immediately when the label equals `_workspace_label_key`.
- Query and update the widget only when the visible label changed.

## Tests

- Extend `tests/test_start_screen.py`.
- Verify same rendered label does not query `#workspace-candidate`.
- Keep changed workspace candidate behavior covered.

## Versioning

Patch release: `1.0.259` -> `1.0.260`.
