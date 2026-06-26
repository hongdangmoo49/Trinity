# Execution Lane Headers

## Problem

The execution page summary shows lane counts, and each row contains compact
`risk gN` or `serial` text. However, the package list itself is still a flat
sequence, so parallel execution groups are not obvious when scanning the page.

## Design

- Keep the existing work-package order and row layout.
- Insert lightweight lane headers before grouped rows:
  - `Lane gN` for parallel groups.
  - `Serial` for non-parallel packages.
- Reuse existing `parallel_group` and `parallelizable` metadata.
- Keep row-level updates intact by only remounting the list when lane membership
  changes.

## Acceptance

- Parallel package rows are visually grouped by lane.
- Serial rows are explicitly labeled.
- Existing row update behavior, compact 80-column layout, and detail actions keep
  working.
