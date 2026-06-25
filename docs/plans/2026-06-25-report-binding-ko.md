# Report Navigation Binding Korean Localization

## Context

The global Textual app bindings localize most Korean footer and command palette labels, but the `ctrl+4` report navigation binding is not mapped.

As a result, Korean UI users can still see `Report` in global navigation chrome while the report screen itself uses `리포트`.

## Scope

- Add a `binding_report` localization key.
- Wire the `ctrl+4` `go_report` binding to the new key.
- Add coverage to the existing app binding localization test.
- Bump the patch version for the PR.

## Validation

- Run the focused binding localization test.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run the full pytest suite before merge.
