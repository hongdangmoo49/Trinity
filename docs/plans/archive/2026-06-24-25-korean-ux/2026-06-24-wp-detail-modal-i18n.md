# Work Package Detail Modal I18n

## Problem

The execution matrix now honors Korean UI mode, but the work-package detail
modal still renders English section titles, field labels, action context text,
and the close button. This makes the execution page feel inconsistent after a
user drills into a package.

## Design

- Pass the execution screen language into `WorkPackageDetailModal`.
- Localize modal chrome only:
  - section headings
  - summary/result/review/spec field labels
  - action context messages
  - close button and escape binding
- Preserve workflow data values such as status, agent names, risk, package ids,
  retry reasons, and review notes.

## Acceptance

- Korean mode shows Korean detail modal chrome and action context labels.
- English mode keeps the previous detail modal text.
- Existing detail modal ordering and execution matrix interactions remain
  unchanged.
