# Retry Disabled Reason Variant Korean Display

## Context

The work package detail modal now localizes `already done`, but snapshot data can
still provide other built-in retry disabled reasons such as `already needs
review`, `does not require execution`, and `status is ...`. These reasons are UI
metadata, not user-authored content, so the Korean Textual UI should render them
consistently.

## Scope

- Add a shared display helper for retry disabled reasons.
- Localize known built-in retry disabled reasons in Korean.
- Keep English output and unknown/custom reasons unchanged.
- Reuse the helper in both work package detail and execution retry surfaces.
- Bump the patch version.

## Validation

- Add regression coverage for Korean retry disabled reason variants.
- Run focused Textual tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run full pytest.
