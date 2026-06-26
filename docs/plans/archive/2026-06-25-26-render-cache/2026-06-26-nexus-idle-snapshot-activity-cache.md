# Nexus Idle Snapshot Activity Cache

## Context

`NexusScreen.apply_snapshot()` calls `_apply_activity_frame()` after every
snapshot render. The frame method then queries provider panels and the central
view even when the snapshot has no running activity surfaces.

`advance_activity_frame()` already avoids this work when no mounted widget is
running. Snapshot application can make the same decision from snapshot data
before touching the widget tree.

## Goal

Skip activity frame application for idle Nexus snapshots.

## Design

- Add a snapshot-level activity predicate.
- Treat the central surface as running when synthesis is `running`/`waiting` or
  the workflow state is one of the live states.
- Treat provider surfaces as running when their projected `ProviderPanelState`
  belongs to the provider panel `running` state group.
- Call `_apply_activity_frame()` from `apply_snapshot()` only when the snapshot
  has activity targets.

## Tests

- Add a focused Nexus activity cache test.
- Verify idle snapshots do not call `_apply_activity_frame()`.
- Verify running provider snapshots still call `_apply_activity_frame()`.

## Versioning

Patch release: `1.0.260` -> `1.0.261`.
