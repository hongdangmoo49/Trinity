# Profile Token Korean Display Labels

## Context

Korean Report, Provider Inspector, and Settings preview surfaces still expose
profile tokens such as `implementer`, `execute`, `execution_v1`, and
`implementation strength`. These are internal profile identifiers, but they are
read as user-facing metadata in the Nexus UI.

## Scope

- Add a shared display helper for known profile/mode/contract/strength tokens.
- Localize known profile tokens only for Korean UI.
- Apply the helper to Report screen, Markdown report export, Provider
  Inspector, Settings preview, and work package routing reason display.
- Keep English UI, persisted config values, and unknown/custom tokens unchanged.
- Bump the patch version.

## Validation

- Run focused report/provider/settings/detail tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run full pytest.
