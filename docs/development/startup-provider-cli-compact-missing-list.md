# Startup Provider CLI Compact Missing List

## Problem

`Provider CLI setup` can become wide when multiple selected providers are
missing. Missing entries include command details such as `antigravity(agy)`, so
three missing providers can make the status notice hard to scan.

Found provider entries only use short agent names. Missing entries need a
smaller visible cap.

## Contract

Keep found providers capped at the existing three visible names, but cap missing
provider CLI entries at two:

```text
Provider CLI setup: selected 3 | missing: claude, codex(codex) +1 | next: fix CLI command/PATH
```

The hidden count still tells the user more selected providers need attention.
The provider inspector/runtime readiness remains the detailed source of truth.

## Non-Goals

- Do not remove command details from the first visible missing entries.
- Do not add a modal.
- Do not change provider readiness runtime behavior.

## Test Plan

- Unit-test three missing provider CLI entries collapse to two plus `+1`.
- Keep existing found/missing and zero-selected tests passing.
- Run focused Start screen tests and required smoke tests.
