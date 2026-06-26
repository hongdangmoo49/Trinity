# Central Panel WP Term Korean Polish

## Context

The Korean central panel still exposes the `WP` abbreviation in action labels and
tooltips. `WP` is useful internally, but in central user actions `작업` or
`작업 패키지` is clearer.

## Scope

- Replace Korean central panel `WP` action labels with clearer `작업` wording.
- Replace Korean central panel tooltips and detail hints with `작업 패키지`.
- Update the Korean refine-work-packages prompt to avoid `WP`.
- Keep English labels and internal action IDs unchanged.
- Update focused central action/refine tests.
- Bump the patch version.

## Validation

- Run focused central panel/refine tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run full pytest.
