# Resume Picker Archive Label Korean Display

## Context

The `/resume` command already uses localized Korean labels for the local command
result table, but the interactive resume picker still renders archive state
values directly, such as `[blueprint_ready]`. Empty goals also fall back to
`(no goal)`, which mixes English into the Korean modal.

## Scope

- Localize resume picker archive state values through the shared status display
  helper.
- Localize the empty-goal fallback for Korean.
- Keep English resume picker labels unchanged.
- Bump the patch version.

## Validation

- Add focused resume picker regression coverage.
- Run focused Textual resume tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run full pytest.
