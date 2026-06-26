# Korean No-Peer Review Wording

## Context

Korean review UI still exposes mixed-language wording such as `peer 없음` and `peer 리뷰어`.

The surrounding UI already uses `동료 리뷰`, so no-peer review labels should use the same Korean term.

## Scope

- Change compact no-peer review status from `peer 없음` to `동료 없음`.
- Change localized no-peer review skip reasons from `peer 리뷰어` to `동료 리뷰어`.
- Keep English labels and internal no-peer detection logic unchanged.
- Update report, execution matrix, and work package detail tests.
- Bump the patch version for the PR.

## Validation

- Run focused review label/report/detail tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run the full pytest suite before merge.
