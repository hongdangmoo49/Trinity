# Question Panel Status Key Normalization

## Context

`QuestionPanel` renders a question status with a fallback:

- explicit `question.status`
- `answered` when an answer exists
- `open` otherwise

The cache key currently stores the raw status field. A snapshot whose status
changes from empty string to `open` produces the same visible UI, but still
forces `_render_questions()`.

## Goal

Align the question panel render cache key with the status value actually shown
on screen.

## Design

- Add a small helper for the rendered question status.
- Use the helper in `_render_questions()`.
- Use the same helper in `_question_key()` so equivalent raw statuses share the
  same key.
- Keep re-rendering when the visible status, answer, options, or text changes.

## Tests

- Add a focused cache test for equivalent empty/open question status values.
- Verify the renderer is skipped for equivalent visible status.
- Verify the renderer still runs for a visible status change.

## Versioning

Patch release: `1.0.265` -> `1.0.266`.
