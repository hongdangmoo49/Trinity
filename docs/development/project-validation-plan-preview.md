# Project Validation Plan Preview

## Problem

Project context detects likely test commands and generation preview now suggests a
first validation command for new projects. However, users still see validation as
a single undifferentiated action.

For both new and existing projects, this creates two practical issues:

- Small exploratory work can feel slower than necessary if users assume every
  step requires a full suite.
- Execution readiness is harder to judge because there is no visible separation
  between a quick smoke check, a PR-required check, and a broader release check.

## Scope

- Add a derived validation plan preview for saved project context.
- Show the preview through `/project` diagnostics near the project-context
  previews.
- Expose the same preview through `trinity project status` text and JSON.
- Derive the plan from saved project context only: detected `test_commands`,
  `build_commands`, `mode`, and new-project starter/profile signals.
- Keep the preview advisory and non-blocking.

## Non-Goals

- Do not execute validation commands.
- Do not edit GitHub Actions or repository CI configuration.
- Do not add new project-intake schema fields.
- Do not block execution when a validation plan is weak.
- Do not introduce a test selection wizard.

## Design

Add a shared `project_validation_plan_label()` helper next to existing
project-intake label helpers. It returns a compact localized line:

- English: `Validation plan: fast ... | required ... | full ...`
- Korean: `검증 계획: 빠른 확인 ... | 필수 확인 ... | 전체 확인 ...`

Derivation rules:

1. `fast`
   - Prefer the first detected test command.
   - For new projects without tests, infer the first smoke check from starter and
     stack signals.
   - For existing projects without tests, show `inspect changed scope`.
2. `required`
   - Prefer all detected test commands, compacted to the existing display limit.
   - If tests are missing but build commands exist, use build commands.
   - Otherwise ask the user/agents to record the required check before merge.
3. `full`
   - Use build commands when both tests and builds exist.
   - Otherwise show a broad but non-executing reminder: full suite before merge
     for existing projects, first scaffold smoke before release for new projects.

This plan is intentionally a label, not a policy engine. It makes cost and
coverage visible before execution without forcing a particular CI setup.

## Tests

- Shared helper returns English and Korean validation plans for new context.
- Existing projects with test/build commands show fast/required/full tiers.
- Context without tests still returns a useful non-blocking plan.
- CLI `project status` text and JSON include the plan.
- `/project` diagnostics refresh the validation plan after project context
  changes.
