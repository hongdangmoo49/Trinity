# Textual Presenter and Parser Contract

This document defines the boundary between the Textual application runtime and
the pure presenter/parser helpers.

## Purpose

The recent Textual cleanup moved many formatting helpers out of
`TrinityTextualApp` and into:

- `src/trinity/textual_app/presenters.py`
- `src/trinity/textual_app/command_parsers.py`
- `src/trinity/textual_app/local_commands.py`

Keep this boundary stable so the app stays focused on runtime wiring, widget
queries, screen transitions, async calls, and state application.

## Presenter Contract

`textual_app.presenters` owns deterministic formatting and UI decision helpers.

Allowed presenter inputs:

- immutable values
- strings, booleans, numbers, and tuples
- snapshot objects such as `WorkflowNexusSnapshot`
- small protocol-shaped objects such as `AgentRowSpec`
- `lang` keyword arguments for English/Korean labels

Allowed presenter outputs:

- strings and Markdown strings
- row tuples for tables
- title/action hint strings
- small frozen dataclasses such as `CentralActionPlan`
- booleans or sets used by widgets to decide visible actions

Presenter functions must not:

- query Textual widgets
- call `refresh`, `mount`, `remove`, or `query_one`
- mutate `WorkflowNexusSnapshot`
- perform filesystem, network, subprocess, or provider calls
- inspect global app state
- schedule async work

## Parser Contract

`textual_app.command_parsers` owns syntax parsing for Textual-owned slash
commands when parsing can be isolated from app state.

Current parser surface:

- `parse_ask_args(args, active_agent_names, lang=...)`
- `AskCommandParseResult`
- `parse_rounds_args(args, lang=..., minimum=..., maximum=...)`
- `RoundsCommandParseResult`
- `parse_agent_args(args, agent_names, lang=...)`
- `AgentCommandParseResult`
- `parse_caveman_args(args, lang=...)`
- `CavemanCommandParseResult`
- `parse_answer_args(args, lang=...)`
- `AnswerCommandParseResult`
- `parse_target_args(args)`
- `TargetCommandParseResult`
- `parse_resume_args(args)`
- `ResumeCommandParseResult`
- `parse_report_args(args)`
- `ReportCommandParseResult`
- `parse_artifact_args(args, lang=...)`
- `ArtifactCommandParseResult`
- `parse_memory_args(args)`
- `MemoryCommandParseResult`
- `parse_execute_args(args)`
- `ExecuteCommandParseResult`

Parser functions may:

- normalize command arguments
- validate agent selectors against an explicit active-agent list
- return localized presenter-generated error strings
- return structured parse results

Parser functions must not:

- read app attributes directly
- mutate app/session state
- call providers or the orchestrator
- emit notifications
- decide whether a parsed command should execute

## Local Command State Contract

`textual_app.local_commands` owns small state transforms and workflow-event
persistence for locally handled slash command results.

Current helper surface:

- `recent_local_command_results(results, limit=...)`
- `snapshot_with_local_command_results(snapshot, results, limit=...)`
- `replace_local_command_result(results, result)`
- `append_local_command_event(state_dir, result, timestamp=...)`

Local command helpers may:

- bound the visible command-result history
- replace an older result for the same slash command
- return a copied `WorkflowNexusSnapshot` with local command results attached
- persist a local slash-command result as a workflow event for report export

Local command helpers must not:

- query Textual widgets
- emit notifications or open modals
- call presenters, providers, or the workflow controller

## App Contract

`TrinityTextualApp` remains responsible for:

- collecting runtime state and snapshots
- calling presenters/parsers
- applying returned strings/rows to widgets
- opening modals and screens
- invoking orchestrator/provider/workflow methods
- persisting or exporting user-visible artifacts
- deciding async control flow and error handling

If a helper needs `self`, widget access, or async runtime state, it belongs in
the app/screen/widget layer rather than `presenters.py`.

## Localization Rule

Presenter/parser helpers should accept `lang: str = "en"` when user-visible text
is returned. Korean labels should reuse `STATUS_CONTEXT_LABELS` or shared display
helpers instead of duplicating ad hoc strings.

## Test Expectations

When changing presenters or parsers, run focused tests first:

```bash
uv run pytest -q tests/test_textual_command_parsers.py tests/test_textual_app.py tests/test_textual_workflow_controller.py
```

For shared local command or snapshot output changes, also run:

```bash
uv run pytest -q tests/test_textual_smoke.py tests/test_textual_runtime.py
```

Run the required smoke gate before pushing broad Textual changes:

```bash
uv run python scripts/run_required_smoke_tests.py -q
```

## Archive Impact

The completed one-PR Textual presenter wrapper plans listed in
`docs/plans/completed-index.md` may be archived once this document and focused
tests cover the active contract.
