# Central Agent Fixed Widget Cache

## Context

`CentralAgentView` is the main Nexus conversation surface. It already avoids
many unnecessary renders with snapshot identity, markdown, local command,
action plan, title, and running-class keys. The remaining update paths still
resolve fixed widgets by selector when the visible state changes.

Because the central view is refreshed from Nexus snapshots and activity ticks,
fixed-widget lookups should be kept out of hot paths where the widget tree is
stable.

## Goal

Cache the fixed central-agent widgets created during compose and reuse them for
snapshot and activity updates.

## Design

- Cache the title `Static`, markdown `Markdown`, local command container
  `Vertical`, action title `Static`, and actions `Grid`.
- Route markdown, local command table, action button, action title, and title
  updates through cache helpers with query fallbacks.
- Reset the cached references before compose so a future recompose cannot hold
  stale widget instances.
- Preserve existing render keys and snapshot identity checks.

## Tests

- Add a focused test that verifies snapshot and activity updates reuse composed
  fixed widgets without selector lookups.
- Keep the existing central markdown, action plan, local command, and title
  update tests intact.

## Versioning

Patch release: `1.0.273` -> `1.0.274`.
