# Provider Panel Korean Metadata Labels

## Context

Provider cards on the Nexus page receive the configured UI language, but their
compact metadata still uses English abbreviations such as `ctx`, `sid`, `out`,
and `q` in Korean UI. These labels are small, yet they sit in the first viewport
and are scanned frequently.

## Scope

- Localize Korean provider card metadata prefixes:
  - `ctx` -> `컨텍스트`
  - `sid` -> `세션`
  - `out` -> `출력`
  - `q` -> `품질`
- Reuse the existing profile token display helper for output contract values.
- Keep English compact provider card metadata unchanged.
- Keep raw session IDs and model/provider values unchanged.
- Bump the patch version.

## Validation

- Run focused provider panel/Nexus provider strip tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run full pytest.
