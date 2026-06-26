# Execution Retry Modal Korean Header Polish

## Context

The Korean execution retry modal still labels the package id column as `WP`.
Other Korean Nexus surfaces now use clearer `작업 패키지` wording, while the
retry modal column specifically contains package IDs such as `WP-001`.

## Scope

- Replace the Korean retry modal package id column header with `작업 ID`.
- Preserve fixed-width table alignment by keeping the first column width stable.
- Keep English modal headers unchanged.
- Keep package ID values such as `WP-001` unchanged.
- Bump the patch version.

## Validation

- Run focused execution retry modal tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run full pytest.
