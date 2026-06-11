# README Workflow and Fresh Install Review

Date: 2026-06-11

Branch: `feature/readme-workflow-install-docs`

Status: completed

## Goal

Review the Korean and English README files against the current workflow
implementation, then document how a new user can install and launch Trinity on
macOS and Windows.

## Sources Reviewed

- `README.md`
- `README.en.md`
- `docs/slash-command-reference.md`
- `docs/plans/2026-06-10-agent-model-selector-cli-discovery.md`
- `docs/plans/2026-06-11-central-agent-provider-session-continuity.md`
- `docs/plans/2026-06-11-wp-non-owner-agent-reviews.md`
- `docs/plans/2026-06-11-final-review-auto-replan.md`
- `src/trinity/workflow/engine.py`
- `src/trinity/workflow/review.py`
- `src/trinity/providers/model_discovery.py`
- `src/trinity/setup/wizard.py`
- `src/trinity/slash_commands.py`

## Differences Found

| Area | README before this update | Current implementation | Documentation action |
| :--- | :--- | :--- | :--- |
| Version | Workflow and project stats referenced `0.10.3`. | Package version is `0.12.7`. | Update version references and avoid brittle exact test counts. |
| Workflow shape | Stops at `ExecutionProtocol.run() -> REVIEWING / DONE`. | The flow now includes WP peer review, review repair, final review, final-review auto replan, resume, and retry. | Expand the workflow model section. |
| Agent targeting | README did not explain per-request selected agents or model overrides. | Start/Nexus UI and `/ask` can target selected agents and carry model overrides into the workflow. | Add target/model selection to runtime rules and TUI features. |
| Model selection | README implied static model choices from config. | `trinity init` and Textual `/model` use provider CLI discovery where available: Codex `debug models`, Antigravity `models`, Claude static fallback. | Document live model discovery and fallback behavior. |
| Provider sessions | README described one-shot provider calls only. | Provider session IDs and runtime model metadata are persisted for worker agents and central synthesis owner keys such as `central:codex`. | Explain one-shot invocation plus session continuity. |
| Question loop | README mentioned questions but not target/model continuity. | Answers reuse the workflow's last selected target agents and model overrides. | Add continuity note. |
| Review behavior | README did not include the new review command and review loop details. | Each completed WP is reviewed by every active non-owner agent; final review falls back `codex -> claude -> antigravity`. | Add WP/final review steps and `/review`. |
| Final review follow-up | README did not mention automatic supplemental planning. | Required final-review `bugfix` and `validation` action items become supplemental `WP-S###` packages and return the workflow to `BLUEPRINT_READY`. | Add final-review auto replan rule. |
| Recovery | README omitted `/execute-retry`. | Failed, blocked, or interrupted work packages can be retried by selector or custom modal. | Add retry command and recovery note. |
| Slash commands | README command table missed `/model`, `/ask`, `/execute-retry`, `/review`, `/improve`, `/memory`, and `/artifact`. | These commands are registered in `src/trinity/slash_commands.py`. | Update both README command tables. |
| First-run setup | README only showed `pip install`, `trinity init`, and `trinity bootstrap`. | New users need platform-specific Python, PATH, provider CLI, auth/trust, and WSL guidance. | Add macOS and Windows fresh install guides. |
| Config comments | README said Codex and Antigravity are disabled by default. | Interactive setup asks for installed providers with default `yes`; non-interactive fallback config still keeps optional providers disabled until explicitly configured. | Clarify interactive vs non-interactive behavior. |

## Current Workflow Summary

1. The user enters a prompt from Start, Nexus, or `/ask`.
2. The selected agents and non-default model overrides are stored in the
   workflow session.
3. `WorkflowEngine` starts, answers, or continues a workflow while preserving
   target agent/model continuity.
4. `TrinityOrchestrator` runs provider deliberation and central synthesis.
5. Provider session IDs and runtime model observations are saved when provider
   CLIs expose them.
6. If central synthesis asks blocking questions, the workflow waits in
   `NEEDS_USER_DECISION`.
7. If a blueprint is ready, Trinity waits for the user to execute or refine.
8. Execution requires target workspace preflight and then runs dependency-safe
   work packages.
9. Completed WPs are reviewed by all active non-owner agents.
10. WP review findings can trigger repair work by the original executor.
11. Final review runs with fallback priority `codex -> claude -> antigravity`.
12. Required final-review fixes are automatically converted into supplemental
    packages and queued for another user-confirmed execution.
13. Resume and `/execute-retry` recover saved or interrupted workflow state.

## Fresh Install Documentation Decisions

- Recommend `pipx install trinity-agent` for end users because it keeps the CLI
  isolated from project dependencies.
- Keep `pip install trinity-agent` as the shortest path for users who already
  manage Python environments.
- For Windows, recommend WSL2 Ubuntu for the same terminal semantics used by
  most Trinity development and provider CLI workflows.
- Explicitly state that provider CLIs must be installed and authenticated in the
  same environment where `trinity` runs. A Claude/Codex/Agy install in Windows
  PowerShell is not automatically available inside WSL.
- Mention that at least one provider CLI is required, while all three provide
  the intended multi-agent workflow.
- Keep provider install URLs instead of hardcoding provider-specific installer
  commands that may change outside this repository.
