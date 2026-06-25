# Korean Action Context Term Polish

## Context

The work package detail modal currently renders the Korean section title `액션 컨텍스트`.

This is understandable but reads like a direct technical loan phrase. `작업 맥락` is shorter and clearer for users inspecting why a package can be retried or what execution context it carries.

## Scope

- Change the Korean work package detail section title from `액션 컨텍스트` to `작업 맥락`.
- Keep English `Action Context` and internal method/key names unchanged.
- Update the focused Korean detail modal test.
- Bump the patch version for the PR.

## Validation

- Run focused work package detail modal tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run the full pytest suite before merge.
