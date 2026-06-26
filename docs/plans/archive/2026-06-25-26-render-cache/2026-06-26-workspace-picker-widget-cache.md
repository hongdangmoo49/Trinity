# Workspace Picker Widget Cache

## Context

`WorkspacePicker` is used before execution and when selecting a target
workspace. It updates a stable set of widgets while users browse directories,
type paths, create folders, and confirm preflight state. Existing logic already
skips unchanged preflight and status text updates, but the picker still resolves
fixed widgets with `query_one()` in several action paths.

The picker layout is stable after compose, so the fixed input, tree, preflight,
and status widgets can be cached.

## Goal

Reduce repeated selector lookups during workspace selection and folder creation
flows.

## Design

- Cache the path input, tree pane, tree placeholder, directory tree, preflight
  text, and status text widgets.
- Route tree mounting, directory selection, folder creation, input path reads,
  tree reload, preflight updates, and status updates through cache helpers with
  query fallbacks.
- Reset widget caches before compose so future recomposition cannot retain
  stale widget references.
- Preserve existing preflight render key and status key equality checks.

## Tests

- Add a focused test that verifies mounted picker actions reuse composed fixed
  widgets without selector lookups.
- Keep existing workspace picker localization, tree root, folder creation, and
  validation tests intact.

## Versioning

Patch release: `1.0.279` -> `1.0.280`.
