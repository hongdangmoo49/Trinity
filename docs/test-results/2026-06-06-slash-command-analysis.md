# Slash Command Analysis Documentation

Date: 2026-06-06

Branch: `codex/slash-command-docs`

## Scope

The task was documentation-first analysis of Trinity slash commands before
adding new convenience features. No runtime command behavior was changed.

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

## Validation

This was a documentation-only change. Validation focused on file references,
Markdown consistency, diff cleanliness, and command-related tests that confirm
the documented router and palette paths still pass.

Commands run:

```bash
git status --short --branch
git diff --check
uv run pytest tests/test_tui_prompt.py tests/test_tui_session.py::TestSessionHandleCommand tests/test_textual_app.py::test_prompt_composer_shows_slash_command_palette tests/test_textual_app.py::test_prompt_composer_localizes_slash_command_palette_in_korean tests/test_textual_app.py::test_nexus_composer_uses_configured_slash_command_language -q
```

Results:

- `git diff --check` passed.
- Slash command focused tests passed: `29 passed in 2.33s`.
