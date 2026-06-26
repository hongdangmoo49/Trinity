# Execution Summary I18n

## Problem

The execution matrix now localizes the main chrome in Korean UI mode, but the
summary bar still mixes English labels such as `lanes`, `serial`, `retry`,
`workflow`, `run`, and `target`.

## Design

- Keep compact status buckets (`RUN`, `REVIEW`, `WAIT`, `DONE`, `ISSUE`) stable.
- Localize descriptive summary labels only:
  - lane count
  - serial count
  - retry count
  - workflow state label
  - run id label
  - target workspace label
- Preserve the summary order and data values.

## Acceptance

- Korean UI mode shows Korean descriptive labels in the execution summary bar.
- English UI mode keeps the existing summary labels.
- Existing execution layout and retry behavior remain unchanged.
