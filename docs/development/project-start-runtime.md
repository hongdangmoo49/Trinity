# Project Start Runtime

## Background

Start and Nexus now expose the same new-project and existing-project setup
surface: target workspace, project intake, continue setup, analyze, create, and
brief actions. The screens currently derive the next setup action independently.

This is risky because a first-run user should see one coherent journey:

1. choose or create the target workspace
2. analyze an existing project or complete a new-project brief
3. plan
4. confirm execution

If Start and Nexus drift, users can be sent to a different next action after
switching screens.

## Goal

- Extract the shared project-start decision into a pure Textual runtime helper.
- Keep Start and Nexus UI layout unchanged.
- Preserve current behavior for new-project and existing-project users.
- Make future setup UX work depend on one decision contract.

## Runtime Contract

Add a small helper module that returns:

- the next setup action: `workspace`, `analyze`, `create`, `brief`, `plan`, or
  `execute`
- target/intake matching checks
- target-missing checks

The helper receives:

- Trinity state directory
- current target workspace text/path
- desired ready action (`plan` on Start, `execute` on Nexus)
- optional analyze action variant provider

It does not render UI and does not mutate state.

## Scope

- Replace duplicated Start/Nexus `_project_setup_next_action` logic with the
  helper.
- Replace duplicated intake target matching and target missing helpers.
- Keep all labels and buttons unchanged.
- Add focused tests around the pure helper and keep existing Start/Nexus tests.

## Non-goals

- Do not change project intake file format.
- Do not add a new screen.
- Do not block execution or planning differently in this slice.
- Do not change provider selection or model discovery behavior.

## Validation

- `uv run pytest tests/test_project_start_runtime.py tests/test_start_screen.py -q`
- `uv run pytest tests/test_textual_app.py -q -k 'project_setup_next_action or project_intake or project_mode_rail'`
- `uv run python scripts/run_required_smoke_tests.py -q`
