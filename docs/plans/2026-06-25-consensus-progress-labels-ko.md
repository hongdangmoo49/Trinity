# Consensus Progress Korean Display

## Context

Nexus snapshots store consensus progress as compact runtime strings such as
`blueprint ready`, `round 1 synthesizing`, or `round 1 consensus not reached
(1/3)`. These raw strings are useful as stable snapshot data, but Korean
Textual surfaces currently render them directly in the central panel, `/context`,
report screen, and markdown export.

## Scope

- Add a display-only consensus progress formatter.
- Localize known built-in progress patterns in Korean.
- Keep English output and unknown custom progress strings unchanged.
- Apply the formatter to central, context, report, and export surfaces.
- Bump the patch version.

## Validation

- Add focused regression coverage for Korean consensus progress displays.
- Run focused Textual presenter/report tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run full pytest.
