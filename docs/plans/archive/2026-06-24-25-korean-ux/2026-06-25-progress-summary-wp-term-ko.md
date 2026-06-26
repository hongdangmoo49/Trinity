# Progress Summary WP Term Korean Polish

## Context

The Korean compact progress summary still displays `WP 없음` and `3 WP` even
though surrounding Nexus Korean UI now uses `작업 패키지`.

## Scope

- Replace the Korean empty progress summary with `작업 패키지 없음`.
- Replace the Korean total count token with `작업 패키지 N개`.
- Keep English compact progress wording unchanged.
- Keep package IDs such as `WP-001` unchanged.
- Bump the patch version.

## Validation

- Run focused progress summary tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run full pytest.
