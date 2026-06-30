# Existing Project Diagnostic Summary

## Background

For existing projects, Trinity already detects useful anchors such as docs, source
roots, entrypoints, package managers, test/dev/build commands, Git state, and possible
subproject scopes. These values are visible across several compact diagnostic
labels, but users do not get one direct "what did Trinity understand about this
project?" summary.

That makes the first existing-project run feel less trustworthy, especially when the
selected target differs from the directory where Trinity was launched.

## Goal

- Add a compact existing-project diagnostic summary to `/project` diagnostics.
- Reuse the existing saved project context analysis data.
- Show the summary only for matching existing-project context.
- Keep new-project surfaces unchanged.

## Summary Content

The diagnostic line should include:

- read anchors: docs and source roots,
- commands: tests, dev, and build signals,
- scope: selected scope, scope candidates, or target root,
- git: branch/dirty state.

Example:

```text
Existing diagnosis: read: README.md, src | tests: uv run pytest | dev: uv run app | build: python -m build | scope: choose apps/web | git: main clean
```

## Non-goals

- Do not run additional filesystem scans from the diagnostic label.
- Do not replace the existing read-first checklist or validation plan.
- Do not show the label for new-project context.

## Validation

- Unit tests for empty/mismatched/new/existing context states.
- Project diagnostic tests that verify the label renders for matching context.
- Required smoke tests before merge.
