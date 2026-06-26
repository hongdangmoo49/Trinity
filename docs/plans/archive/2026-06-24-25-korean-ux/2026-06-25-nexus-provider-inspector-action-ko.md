# Nexus Provider Inspector Action Label Korean Polish

## Context

The Korean Nexus action bar labels mostly describe direct actions, but the provider inspector button is currently a noun phrase: `프로바이더 인스펙터`.

Because this button opens a modal, the Korean UI should make the action explicit without changing the modal title or English labels.

## Scope

- Change the Korean Nexus action bar button label to `프로바이더 인스펙터 열기`.
- Keep the Provider Inspector modal title as `프로바이더 인스펙터`.
- Update the existing Korean Nexus action bar test.
- Bump the patch version for the PR.

## Validation

- Run the focused Nexus Korean action bar test.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run the full pytest suite before merge.
