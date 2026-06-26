# Korean Status Spacing Polish

## Context

Several Korean UI surfaces still render compact status text such as `실행중` and `리뷰중`.

Korean user-facing labels are easier to scan when these status phrases use natural spacing: `실행 중`, `리뷰 중`.

## Scope

- Change shared Korean status values for `running` and `reviewing`.
- Change the Korean execution matrix summary label from `실행중` to `실행 중`.
- Change the central agent progress label from `실행중` to `실행 중`.
- Keep compact button/status groups that intentionally use short nouns unchanged.
- Update focused tests for history, status rows, execution retry, reports, and execution matrix summary.
- Bump the patch version for the PR.

## Validation

- Run focused Korean status/rendering tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run the full pytest suite before merge.
