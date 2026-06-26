# Korean Output Contract Term Polish

## Context

The Korean UI currently translates `output contract` as `출력 계약`.

That phrase reads like a legal contract rather than a provider response schema/format. `출력 형식` is clearer in Provider Inspector and Settings preview surfaces.

## Scope

- Change Provider Inspector Korean label from `출력 계약` to `출력 형식`.
- Change Settings preview Korean label from `출력 계약` to `출력 형식`.
- Keep English labels and internal field names unchanged.
- Update focused tests for Provider Inspector and Settings preview.
- Bump the patch version for the PR.

## Validation

- Run focused Provider Inspector and Settings preview tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run the full pytest suite before merge.
