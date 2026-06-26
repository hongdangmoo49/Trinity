# Korean Fallback Term Polish

## Context

The Korean execution UI currently shows the technical loanword `폴백` for fallback executors and fallback attempts.

For end users, `대체` is clearer and shorter while preserving the same meaning.

## Scope

- Change Korean fallback executor suffix from `폴백` to `대체`.
- Change Korean work package detail label from `폴백 시도` to `대체 시도`.
- Keep English labels and internal fallback logic unchanged.
- Update execution matrix and retry modal tests.
- Bump the patch version for the PR.

## Validation

- Run focused execution retry and matrix display tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run the full pytest suite before merge.
