# Korean Profile Revision Term Polish

## Context

The work package detail modal uses `프로필 리비전` in Korean.

`리비전` is understandable to developers, but `버전` is clearer and more natural in a user-facing detail view.

## Scope

- Change the Korean work package detail label from `프로필 리비전` to `프로필 버전`.
- Keep English `Profile revision` and internal `profile_revision` field names unchanged.
- Add Korean detail modal coverage for the label.
- Bump the patch version for the PR.

## Validation

- Run focused work package detail modal tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run the full pytest suite before merge.
