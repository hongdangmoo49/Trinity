# Startup Provider CLI Action Hint

## Problem

The provider CLI setup notice now shows missing provider commands, but a
first-time user still needs to infer the recovery action. For example,
`missing: codex(codex)` tells them what is absent, but not whether they should
install the CLI, fix PATH, or update `cli_command`.

## Contract

When any selected provider CLI is missing, append one compact next-action hint:

```text
Provider CLI setup: selected 2 | found: claude | missing: codex | next: fix CLI command/PATH
```

Korean:

```text
프로바이더 CLI 설정: 선택 2개 | 발견: claude | 없음: codex | 다음: CLI 명령/PATH 수정
```

When no provider CLI is missing, keep the current concise label unchanged.

## Non-Goals

- Do not add provider-specific install URLs to the compact status notice.
- Do not run provider commands.
- Do not change provider readiness runtime behavior.
- Do not add a modal.

## Test Plan

- Unit-test that the action hint appears only when missing CLIs exist.
- Update provider notice tests for the appended hint.
- Run focused Start screen tests and required smoke tests.
