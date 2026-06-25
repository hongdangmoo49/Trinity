# Start Screen Widget Cache

## Context

`StartScreen` is the first workbench surface and coordinates the initial prompt,
agent/model selector, and optional target workspace label. It already skips
unchanged workspace label updates, but actions still resolve fixed widgets with
`query_one()` when focusing or clearing the composer, reading selected agents,
applying model choices, and updating the workspace label.

The layout is stable after compose, so these fixed child widgets can be cached.

## Goal

Reuse the composed start screen composer, recipient selector, and workspace
label widgets for user actions and workspace/model updates.

## Design

- Cache `PromptComposer`, `AgentRecipientModelSelector`, and workspace label
  `Static` during compose.
- Route mount focus, model choice application, submit actions, slash command
  clearing, empty prompt focus, and workspace label updates through cache
  helpers with query fallbacks.
- Reset caches before compose so future recomposition cannot hold stale widget
  references.
- Preserve the existing workspace label render key and unchanged update skips.

## Tests

- Update workspace label query expectations to verify changed labels use the
  cached widget.
- Add a focused test covering composer and selector access through the cached
  widgets.
- Keep existing workspace label update tests intact.

## Versioning

Patch release: `1.0.277` -> `1.0.278`.
