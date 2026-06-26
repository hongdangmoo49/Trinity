# Report and Presenter WP Term Korean Polish

## Context

Recent Nexus polish replaced user-facing Korean `WP` abbreviations in the
central panel. The same abbreviation still appears in local command presenters,
Markdown report export labels, and report screen section translations.

## Scope

- Replace Korean local presenter labels and hints that use `WP` as prose with
  `작업 패키지`.
- Replace Korean Markdown report export labels such as running/done package and
  routing headings with `작업 패키지` wording.
- Replace Korean report screen translations for central/local work package graph
  headings.
- Keep English labels, internal keys, slash command names, and package IDs such
  as `WP-001` unchanged.
- Bump the patch version.

## Validation

- Run focused presenter/report tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run full pytest.
