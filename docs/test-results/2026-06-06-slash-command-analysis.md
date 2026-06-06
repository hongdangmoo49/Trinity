# Slash Command Analysis Documentation

Date: 2026-06-06

Branch: `codex/slash-command-docs`

## Scope

The task was documentation-first analysis of Trinity slash commands before
adding new convenience features. Runtime command execution behavior was not
changed; the follow-up patch only improved slash command discoverability.

## Code Paths Reviewed

| Area | Files |
| :--- | :--- |
| Plain TUI command router | `src/trinity/tui/session.py` |
| Prompt completion command list | `src/trinity/tui/prompt.py` |
| Textual slash palette | `src/trinity/textual_app/widgets/composer.py` |
| Textual Nexus event flow | `src/trinity/textual_app/screens/nexus.py`, `src/trinity/textual_app/app.py` |
| Textual workflow bridge | `src/trinity/textual_app/workflow_controller.py` |
| Localized palette descriptions | `src/trinity/textual_app/i18n.py` |
| Workflow state and execution side effects | `src/trinity/workflow/engine.py`, `src/trinity/workflow/decomposer.py` |

## Documentation Added

- `docs/slash-command-reference.md`
  - Defines the current slash command execution surfaces.
  - Documents plain TUI routing with `shlex.split()`.
  - Separates Textual Workbench slash palette behavior from executable commands.
  - Lists every current plain TUI slash command, its usage, state mutation level,
    and side effects.
  - Records persistence paths and event files affected by workflow commands.
  - Captures current inconsistencies and recommended next implementation direction.

## Documentation Updated

- `README.md`
  - Expanded the TUI inline command table to include workflow, question, target,
    execution, report, package, and alias commands.
  - Added a link to the new detailed reference.
- `README.en.md`
  - Mirrored the expanded command table and reference link.
- `docs/workflow-v0.10.2-guide.md`
  - Added the slash command reference as the detailed source of truth.
  - Documented the current Textual palette limitation: it suggests slash commands
    but does not execute `/status`-style command actions.
- `docs/checkpoint.md`
  - Added the new reference to the current operating documentation list.

## Discoverability Follow-up

- Added `/report`, `/exit`, and `/q` to `TRINITY_COMMANDS` so prompt_toolkit
  completion and the Textual slash palette expose the plain TUI commands that
  already worked.
- Added localized Textual descriptions for `/report`, `/exit`, and `/q`.
- Updated command reference notes so the remaining gap list reflects the current
  branch state.

## Findings

1. Plain TUI is the only complete slash command execution router today.
2. Textual Workbench has slash command discovery/completion, but submitted slash
   text is currently treated as Nexus follow-up text.
3. Textual execution is correctly wired through `Execute` / `Ctrl+E`, not through
   a general slash command router.
4. `/report` exists in the plain TUI handler but is not present in the shared
   completion list or Textual localized command descriptions.
5. `/exit` and `/q` are accepted aliases for `/quit` in plain TUI but are not
   advertised by completion.
6. `/rounds`, `/agent`, and `/caveman` mutate the in-memory session config only;
   they do not persist settings to disk.

## Textual Slash Routing Follow-up

Observed symptom:

- On the first Textual page, typing `/status`, `/workflow`, or another slash
  command can move the app to Nexus and start agent deliberation.
- On the Nexus page, submitting a slash command can be treated as a follow-up and
  can call agents depending on the workflow state.

Root cause:

- `PromptComposer` only shows and inserts slash command candidates.
- `StartScreen` posts every non-empty composer submission as
  `StartScreen.Submitted`.
- `NexusScreen` posts every non-empty composer submission as
  `NexusScreen.FollowUpSubmitted`.
- `TrinityTextualApp` then calls `TextualWorkflowController.start_prompt()` or
  `submit_follow_up()` without first checking whether the text is a local slash
  command.

Required routing policy:

| Command class | Agent call allowed | Examples |
| :--- | :--- | :--- |
| Local/UI read-only | No | `/help`, `/status`, `/context`, `/history`, `/workflow`, `/questions`, `/decisions`, `/packages`, `/subtasks`, `/report` |
| Local file write | No | `/save`, `/report save` |
| Session setting mutation | No | `/rounds`, `/agent`, `/caveman` |
| Workflow local mutation | No by default | `/target`, `/resume` |
| Conditional re-deliberation | Only after workflow action requests it | `/answer` |
| Explicit execution | Yes | `/execute` |
| Unknown slash command | No | `/anything-else` |

Next implementation should add a Textual slash command router before
`start_prompt()` and `submit_follow_up()`. Tests should prove that `/status`,
`/workflow`, `/questions`, and unknown slash commands do not invoke the
orchestrator from either Start or Nexus.

## Validation

Validation focused on file references, Markdown consistency, diff cleanliness,
and command-related tests that confirm the documented router and palette paths
still pass.

Commands run:

```bash
git status --short --branch
git diff --check
uv run pytest tests/test_tui_prompt.py tests/test_tui_session.py::TestSessionHandleCommand tests/test_textual_app.py::test_prompt_composer_shows_slash_command_palette tests/test_textual_app.py::test_prompt_composer_localizes_slash_command_palette_in_korean tests/test_textual_app.py::test_nexus_composer_uses_configured_slash_command_language -q
```

Results:

- `git diff --check` passed.
- Slash command focused tests passed: `29 passed in 2.68s`.
