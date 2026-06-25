# Execution Matrix Second Review Korean Spacing

## Context

The Korean execution matrix uses compact second-review labels such as `2차리뷰`, `2차실행`, and `2차필요`.

Other Korean surfaces already use the clearer `2차 리뷰 필요` wording, so the execution matrix should use readable spacing where button width allows it.

## Scope

- Change Korean second-review detail action label to `2차 리뷰`.
- Change Korean second-review run action label to `2차 실행`.
- Change Korean compact status label to `2차 필요`.
- Keep English labels unchanged.
- Update focused execution matrix tests.
- Bump the patch version for the PR.

## Validation

- Run focused execution matrix label tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run the full pytest suite before merge.
