# Target Workspace Korean Term Alignment

## Context

The Start and Nexus screens use `작업 폴더` for workspace selection, but `/target` command results and workflow outcome messages still use `워크스페이스`.

This makes the same concept appear under two Korean terms in the interactive UI.

## Scope

- Align Korean `/target` command result labels and hints to `작업 폴더`.
- Align Korean workflow outcome messages that ask for a target workspace to `대상 작업 폴더`.
- Keep command names such as `/target` and English messages unchanged.
- Update existing presenter and Textual tests.
- Bump the patch version for the PR.

## Validation

- Run focused presenter and Nexus `/target` tests.
- Run `git diff --check`.
- Run `uv run trinity --version`.
- Run the full pytest suite before merge.
