# Startup Provider CLI Command Detail

## Problem

The provider CLI setup notice reports which selected providers have a
missing CLI. For agents whose name differs from the actual command, the missing
entry is not actionable enough. The most visible case is Antigravity: the agent
is named `antigravity`, but Trinity invokes `agy`.

## Contract

When a missing provider uses a command that differs from the agent name, include
the command in parentheses:

```text
Provider CLI setup: selected 2 | missing: antigravity(agy)
```

Keep same-name commands concise:

```text
Provider CLI setup: selected 1 | missing: codex
```

For configured paths, show only the basename:

```text
missing: reviewer(custom-cli.exe)
```

## Non-Goals

- Do not show full local paths in the compact startup label.
- Do not run provider commands.
- Do not change runtime readiness behavior.

## Test Plan

- Unit-test missing command details for same-name and different-name commands.
- Update provider notice tests for the changed missing CLI text.
- Run focused Start screen tests and required smoke tests.
