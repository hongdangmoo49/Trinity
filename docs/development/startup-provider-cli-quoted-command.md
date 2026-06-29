# Startup Provider CLI Quoted Command Parsing

## Problem

The startup provider CLI setup hint extracts the executable from
`AgentSpec.cli_command`. It handles plain commands such as `codex` and quoted
commands that contain only the executable path. However, a custom setup can use a
quoted executable plus arguments:

```text
"/path with spaces/custom-cli" --profile work
```

In that shape, the current parser treats the whole string as the path-like
executable. The setup hint can then report the provider as missing even when the
actual executable path exists.

## Contract

For the lightweight Start/Nexus CLI setup hint:

- If `cli_command` starts with a quote, extract text up to the matching closing
  quote as the executable.
- Ignore trailing arguments after that closing quote.
- Preserve existing behavior for plain commands and path-like commands.
- Do not execute provider CLIs.

## Non-Goals

- Do not support unquoted paths with spaces and trailing arguments. Those are
  ambiguous and should be configured with quotes or `extra_args`.
- Do not change provider runtime readiness behavior in this pass.
- Do not validate argument syntax.

## Test Plan

- Unit-test quoted command plus trailing args resolves to the quoted executable.
- Unit-test display command uses the quoted executable basename.
- Run focused Start screen tests and required smoke tests.
