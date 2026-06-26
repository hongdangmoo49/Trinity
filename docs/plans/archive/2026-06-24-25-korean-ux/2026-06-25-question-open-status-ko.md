# Question Panel Open Status Korean Label

## Context

The Nexus question panel localizes status tokens, but unanswered questions are
shown as `[열림]`. That is a literal state label and does not clearly communicate
that the user needs to answer the question.

## Scope

- Change the Korean `open` question status label to `답변 대기`.
- Keep English output unchanged.
- Keep answered-question labeling unchanged.
- Bump the patch version.

## Validation

- Update focused QuestionPanel regression coverage.
- Run focused Textual question tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run full pytest.
