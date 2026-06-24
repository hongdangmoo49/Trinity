# Fake Provider CI Smoke

## Problem

Trinity has a deterministic fake provider harness for `claude`, `codex`, and
`agy`, but the default pull request smoke workflow did not run it. Provider CLI
contracts could regress without being caught on all supported platforms.

## Design

- Keep fake providers account-free and token-free.
- Run `tests/test_fake_provider_harness.py` in the cross-platform smoke workflow.
- Run the same harness before PyPI publishing so release automation verifies the
  provider abstraction without real user credentials.
- Make the fake binaries executable on Windows by exposing `.cmd` wrappers that
  invoke the generated Python scripts.

## Acceptance

- Ubuntu, macOS, and Windows PR smoke jobs execute the fake provider harness.
- Publish preflight tests also execute the fake provider harness.
- The fake CLI paths remain command-like on POSIX and `.cmd`-based on Windows.
- Local focused tests pass with `uv run pytest tests/test_fake_provider_harness.py -q`.
