# Retry Disabled Reason Korean Display

## Context

Work package detail labels are localized in Korean, but the retry disabled
reason is rendered from raw snapshot data. When a completed package is not
retryable, the detail modal can show `재시도 불가: already done`, mixing Korean
labels with an English internal reason.

## Scope

- Localize known retry disabled reasons in the work package detail modal.
- Start with the current built-in reason `already done`.
- Keep English UI and unknown/custom retry disabled reasons unchanged.
- Keep snapshot data unchanged.
- Bump the patch version.

## Validation

- Run focused work package detail tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run full pytest.
