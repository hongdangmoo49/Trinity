# Execution Retry Modal I18n

## Problem

The Nexus execution retry flow can now be reached directly from the central
panel. In Korean UI mode, the retry modal still renders English chrome such as
`Execute Retry`, `Retry selected`, and `Selected: (none)`.

## Design

- Localize only modal UI labels and helper text.
- Preserve work-package data values such as status, topic, owner, and retry
  notes because they come from workflow state.
- Keep selectors stable (`all`, `failed`, `blocked`, `interrupted`, `custom`) so
  controller behavior does not change.

## Acceptance

- Korean mode renders Korean modal title, filter labels, summary labels, action
  labels, and selected text.
- English mode keeps the existing labels.
- Retry selection behavior remains unchanged.
