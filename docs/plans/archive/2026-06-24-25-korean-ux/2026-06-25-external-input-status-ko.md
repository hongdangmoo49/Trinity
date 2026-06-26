# External Input Status Korean Display

## Context

Work package detail status values use shared status labels, but
`waiting_for_external_input` is currently treated as an unknown custom value and
renders raw in Korean UI. This status is user-facing enough to deserve a known
display label.

## Scope

- Add a Korean status display label for `waiting_for_external_input`.
- Keep English output and truly unknown custom statuses unchanged.
- Update regression coverage for the new known status.
- Bump the patch version.

## Validation

- Run focused work package detail status tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run full pytest.
