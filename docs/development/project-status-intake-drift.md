# Project Status Context Drift

This design extends `trinity project status` after the execute-preflight drift
gate landed.

## Problem

Execute Preflight now warns when saved existing-project context differs from the
live workspace. That protects the final execution step, but CLI users should be
able to see the same condition before opening the Textual workbench or pressing
execute.

## Contract

`trinity project status` should report whether matching existing-project context
has drifted from the current workspace profile.

For changed existing-project context:

- human output shows an analysis changed line and recommends
  `trinity project status --refresh`;
- JSON readiness includes `analysis_changed` and `analysis_changed_fields`;
- JSON `workbench_next_step` becomes `describe_analysis` for the simplified
  prompt-led Workbench flow;
- JSON `next_steps` starts with `trinity project status --refresh`.

Missing targets, incomplete new-project briefs, stale analysis, and sparse
analysis keep their existing precedence.

## Scope

The check reuses the same cheap read-only signals as Execute Preflight:

- Git repository flag, branch, dirty count, and untracked count.
- Package managers.
- Test, dev, and build command suggestions.
- Entrypoints.
- Source roots.
- Documentation anchors.

The status command must not execute package managers, tests, build tools, or user
code.

## Tests

Coverage should prove:

- unchanged existing-project context keeps `analysis_changed` false;
- changed analysis anchors are shown in human output and JSON;
- drift recommends `trinity project status --refresh`;
- `--refresh` clears the drift because the saved context is rewritten.
