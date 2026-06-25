# Nexus Screen Widget Cache

## Context

`NexusScreen` coordinates the provider strip, central agent view, question
panel, workflow inspector, recipient selector, workspace label, and composer.
Several child widgets already cache their own render state, but the screen still
resolves those fixed children through selector queries during snapshot updates,
direct provider updates, activity ticks, and follow-up submission.

This screen receives frequent workflow snapshots, so screen-level fixed-widget
lookups should be avoided once the layout is composed.

## Goal

Cache stable Nexus child widgets created during compose and reuse them for
workflow updates and user actions.

## Design

- Cache provider panels by provider name while composing the provider strip.
- Cache the workspace label, central agent view, question panel, inspector,
  recipient/model selector, and composer.
- Route snapshot application, direct provider updates, workspace label refresh,
  follow-up submission, selection/model updates, and activity ticks through
  cache helpers with query fallbacks.
- Reset caches before compose so a future recompose cannot retain stale widget
  references.
- Preserve existing provider state, snapshot identity, workspace label, and
  activity-frame caches.

## Tests

- Update direct provider state cache expectations so changed updates use the
  cached provider panel.
- Add a focused Nexus screen test that verifies snapshot refresh, workspace
  label refresh, composer/selector access, and activity ticks reuse composed
  widgets without fixed selector lookups.
- Keep existing Nexus provider, workspace, agent selection, and activity-frame
  tests intact.

## Versioning

Patch release: `1.0.275` -> `1.0.276`.
