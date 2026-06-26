# Prompt Composer Widget Cache

## Context

`PromptComposer` is shared by the Start and Nexus screens. It already caches
command palette render keys, row states, overflow state, palette visibility, and
same-text updates. The remaining hot paths still resolve the composed text area,
command palette, command option rows, and overflow row through `query_one()`.

Since the composer layout is stable after compose, these fixed widgets can be
cached once and reused during typing, slash-command palette updates, submit, and
focus actions.

## Goal

Avoid repeated selector lookups in PromptComposer input and command palette
paths.

## Design

- Cache `ComposerTextArea`, command palette `Vertical`, command option rows, and
  the overflow `Static` during compose.
- Route text reads/writes, focus, newline insertion, palette visibility, option
  row updates, and overflow updates through cache helpers with query fallbacks.
- Reset widget caches before compose so future recomposition cannot retain stale
  widget references.
- Preserve existing command palette render keys and row-state equality checks.

## Tests

- Update command option movement expectations so changed rows use cached option
  widgets without selector lookups.
- Add a focused test that verifies text area and palette actions reuse composed
  widgets.
- Keep existing palette render, visibility, same-text, and paste-clear tests
  intact.

## Versioning

Patch release: `1.0.280` -> `1.0.281`.
