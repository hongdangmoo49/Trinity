# Execution Lane Korean Term Alignment

## Context

The Korean execution UI currently exposes the term `레인` for parallel execution lanes.

The term is accurate internally, but `그룹` is clearer for users reading the execution matrix, report screen, exported report, and work package detail modal.

## Scope

- Change Korean execution matrix lane labels from `레인` to `그룹`.
- Change Korean report and markdown export routing labels from `레인` to `그룹`.
- Change Korean work package detail label from `실행 레인` to `실행 그룹`.
- Keep English labels and internal data/model names unchanged.
- Update tests for the Korean visible text.
- Bump the patch version for the PR.

## Validation

- Run focused execution matrix, report, export, and work package detail tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run the full pytest suite before merge.
