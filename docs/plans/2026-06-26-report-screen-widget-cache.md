# Report Screen Widget Cache

## Context

`ReportScreen` renders a fixed export status widget and a fixed report body
container. Export status updates and report body re-renders currently resolve
these widgets with `query_one()` each time.

The screen already skips identical report sources and identical render ids, so
this change targets the remaining fixed-widget lookup cost on valid updates.

## Goal

Avoid repeated selector lookups for fixed report screen widgets.

## Design

- Cache the export status `Static` widget during compose.
- Cache the report body `VerticalScroll` container during compose.
- Route `show_export_path()` and `_render_report()` through cache helpers with
  query fallbacks.
- Preserve existing render-id and export-status text caches.

## Tests

- Extend report screen cache tests to verify export status updates use the
  cached widget.
- Verify report body renders use the cached body container.
- Keep existing report identity cache tests intact.

## Versioning

Patch release: `1.0.269` -> `1.0.270`.
