# Report Synthesis Source Korean Display

## Context

The report synthesis section now localizes consensus progress, but its source
field still renders raw metadata values such as `runtime`, `workflow`, and
`shared.md`. Trinity already has a shared source display helper, so the report
surfaces should use it consistently.

## Scope

- Expand source display labels for synthesis source values.
- Apply source display labels to the report screen synthesis section.
- Apply source display labels to markdown report export.
- Keep English output and unknown custom source values unchanged.
- Bump the patch version.

## Validation

- Add focused Korean report/source regression coverage.
- Run focused report tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run full pytest.
