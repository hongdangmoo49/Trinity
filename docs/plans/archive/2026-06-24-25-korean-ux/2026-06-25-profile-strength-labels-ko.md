# Profile Strength Korean Label Coverage

## Context

The profile token display helper localizes common provider profile values, but
the default Korean Settings preview still shows `architecture 0.95` for Claude.
Other built-in strengths such as `documentation`, `research`, and `refactor`
can also appear on provider summaries.

## Scope

- Extend Korean profile token labels for built-in strength names:
  `architecture`, `documentation`, `enhancement`, `refactor`, and `research`.
- Keep English profile token display unchanged.
- Add a Korean Settings preview regression assertion for the Claude strength.
- Bump the patch version.

## Validation

- Run focused settings/display label tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run full pytest.
