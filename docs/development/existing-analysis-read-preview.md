# Existing Analysis Read Preview

Status: Superseded by the simplified Workbench flow. Start/Nexus no longer show
an `Analyze Existing` action or analysis preview step; workspace context is
shown through compact labels and provider prompt context.

## Problem

Existing-project analysis records docs, source roots, and test commands. The
Workbench summary already includes those fields, but users still need to scan a
long line to understand where Trinity expects agents to start reading.

After pressing `Analyze Existing`, the UI should provide a compact preview of
the most useful read anchors.

## Scope

- Add a compact `read first` preview to existing-project intake labels when
  docs or source roots are detected.
- Keep new-project labels unchanged.
- Keep the full existing tests, dev, build, source, entrypoint, and docs
  sections unchanged.
- Do not change project-intake persistence, detection, readiness policy,
  prompts, or preflight gates.

## Design

In `workspace_labels.py`, derive read anchors from:

- `docs_found`
- `source_roots`

For existing projects, render a localized section:

- English: `read first: README.md, docs, src +N`
- Korean: `먼저 읽기: README.md, docs, src +N`

The preview is intentionally duplicated from the full profile sections. It is a
scannability affordance, not a replacement for the detailed profile fields.

## Tests

- Existing-project labels with docs/source roots include `read first`.
- Korean labels include `먼저 읽기`.
- Sparse existing-project labels do not show read preview.
- New-project labels do not show read preview.
