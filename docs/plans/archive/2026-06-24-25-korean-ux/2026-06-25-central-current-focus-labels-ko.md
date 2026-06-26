# Central Current Focus Korean Labels

## Context

The Central Agent current-focus section is localized at the heading level, but
the row content still renders raw execution metadata. Korean Nexus can show
`[blocked]` and `Blockers: ... +1 more`, which mixes internal English labels
with the Korean UI.

## Scope

- Render the existing current-focus runtime detail section in the central panel.
- Localize current-focus work package status values.
- Localize the blockers label.
- Localize the compact remaining-count suffix for blockers.
- Keep English output unchanged.
- Bump the patch version.

## Validation

- Add focused CentralAgentView regression coverage.
- Run focused CentralAgentView tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run full pytest.
