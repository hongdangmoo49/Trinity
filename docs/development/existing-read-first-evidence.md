# Existing Project Read-First Evidence

Date: 2026-06-29
Branch: `feature/existing-read-first-evidence`

## Problem

Existing-project onboarding records docs, source roots, entrypoints, scope, and
validation commands. The execution confirmation context currently shows the
read-first state, but not the concrete anchors that Trinity expects agents to
inspect.

Users need to see evidence that the selected project, not the Trinity control
repository, is the source of truth.

## Goal

Expose read-first anchors in the existing-project context summary before agents
plan or execute.

## User Experience

1. User analyzes an existing project.
2. Trinity records docs/source/entrypoint anchors in project intake.
3. Execution confirmation shows a compact `read` item such as
   `read: README.md, src, +1`.
4. If no anchors are available, the summary says `read: missing`.

## Implementation Plan

- Extend the project context summary labels with a read anchor label.
- Add a read anchor item for existing-project summaries.
- Derive the item from `docs_found`, `source_roots`, and `entrypoints`.
- Keep new-project summaries unchanged.
- Add tests for populated and missing anchors.

## Non-Goals

- Do not execute file reads.
- Do not change provider prompts in this slice.
- Do not redesign the anchor review modal.

## Success Criteria

- Existing-project context summaries include concrete read anchors when present.
- Existing-project context summaries say read is missing when no anchors exist.
- New-project context summaries are unchanged.
- Tests and required smoke pass.
