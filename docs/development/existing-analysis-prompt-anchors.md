# Existing Analysis Prompt Anchors

Status: Superseded by the simplified Workbench flow. Start/Nexus no longer seed
analysis prompts from a Workbench `Analyze Existing` action; users express
analysis intent directly in the prompt.

## Problem

After `Analyze Existing`, the Workbench summary can show concrete read anchors
such as README, docs, and source roots. The seeded Start/Nexus prompt still uses
generic wording: read docs, source roots, and test/build signals. That leaves
agents without the concrete anchors Trinity just detected unless they inspect
the intake artifact separately.

## Scope

- Add detected existing-project anchors to the seeded analysis prompt.
- Use saved intake fields only:
  `docs_found`, `source_roots`, `test_commands`, `dev_commands`, and
  `build_commands`.
- Keep new-project prompts unchanged.
- Do not change project-intake detection, persistence, readiness policy, or
  preflight gates.

## Design

`_sync_project_intake_for_target` should return the `ProjectIntake` it writes.
Direct existing-project analysis paths pass that intake to
`_seed_start_prompt_for_existing_analysis` or
`_seed_nexus_prompt_for_existing_analysis`.

`_existing_project_analysis_prompt` appends a compact localized block when
signals are available:

- English: `Detected anchors: read first ..., tests ..., dev ..., build ...`
- Korean: `감지된 앵커: 먼저 읽기 ..., 테스트 ..., 개발 ..., 빌드 ...`

The block remains advisory. It helps the first response start from concrete
project context without changing workflow execution semantics.

## Tests

- Start `Analyze Existing` prompt includes detected docs/source/test/dev/build
  anchors.
- Nexus `Analyze Existing` prompt includes the same detected anchors.
- Sparse existing-project analysis still produces the target-aware generic
  prompt without an empty anchor block.
