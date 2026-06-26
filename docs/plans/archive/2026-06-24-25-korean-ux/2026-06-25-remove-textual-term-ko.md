# Remove Textual Implementation Term From Korean UI

## Context

Some Korean UI messages expose the implementation term `Textual` to end users.

This is useful internally, but in visible Korean UX it reads like framework jargon and is inconsistent with user-facing Trinity terminology.

## Scope

- Replace Korean `Textual` history empty-state wording with `현재 세션`.
- Replace Korean save guidance with `Trinity 워크플로우` and `마크다운`.
- Remove `Textual` from Korean quit confirmation body text.
- Keep English strings and internal names unchanged.
- Update tests to prevent the framework term from leaking back into Korean UI.
- Bump the patch version for the PR.

## Validation

- Run focused presenter, history, save, and quit modal tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run the full pytest suite before merge.
