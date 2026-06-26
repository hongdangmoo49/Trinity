# Modal chrome i18n

Date: 2026-06-24
Branch: ux/modal-chrome-i18n

## Problem

Several Textual modals still render English chrome labels in Korean mode:

- Resume workflow picker title, empty state, and cancel button
- Quit confirmation title, body, and buttons
- Control repository target confirmation title, body, path labels, and buttons

## Scope

- Add small label dictionaries to the three modal widgets.
- Pass the configured app language when opening quit and target confirmation modals.
- Keep paths, workflow IDs, and user data unchanged.

## Verification

- Add Korean modal chrome tests for resume, quit, and target confirmation.
- Run focused modal tests, Textual app tests, full test suite, diff check, and version check.
