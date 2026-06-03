# Trinity v0.7.0 Smoke Test Checklist

> Multi-Agent Workflow Engine — WSL / Linux / macOS + tmux

Date: 2026-06-03
Version: v0.7.0
Document: WSL/tmux Smoke Test Checklist

---

## 1. Environment Prerequisites

| # | Item | Requirement | Verified |
|---|------|-------------|----------|
| 1.1 | Operating system | WSL2 (Ubuntu 22.04+), native Linux, or macOS 13+ | |
| 1.2 | tmux | >= 3.0 (`tmux -V`) | |
| 1.3 | Python | >= 3.10 (`python3 --version`) | |
| 1.4 | uv | Installed (`uv --version`) | |
| 1.5 | Claude Code CLI | Installed and authenticated (`claude --version` then run `claude` to confirm prompt appears) | |
| 1.6 | Codex CLI (if enabled) | Installed and authenticated (`codex --version` then run `codex` to confirm prompt appears) | |
| 1.7 | Gemini CLI (if enabled) | Installed and authenticated (`gemini --version` then run `gemini` to confirm prompt appears) | |
| 1.8 | Project dependencies | `uv sync` completes without error | |
| 1.9 | Trinity config | `.trinity/trinity.config` present (run `uv run trinity init` if missing) | |
| 1.10 | Git worktree (if used) | No stale worktrees from prior runs (`git worktree list`) | |
| 1.11 | No stale tmux sessions | `tmux list-sessions` shows no `trinity` session (kill with `tmux kill-session -t trinity` if present) | |

### Pre-check commands

```bash
cd /path/to/Trinity
tmux -V                    # expect >= 3.0
python3 --version          # expect >= 3.10
uv --version               # expect any recent
uv sync                    # install deps
uv run trinity --version   # expect v0.7.0

# Authenticate each provider in a separate terminal first:
claude                      # should show prompt, not auth screen
codex                       # should show prompt, not auth screen
gemini                      # should show prompt, not auth screen
```

---

## 2. Pre-flight Checks

These verify that `uv run trinity` starts correctly and `ProviderReadinessGate` works.

| # | Test Step | Expected Result | Pass/Fail | Notes |
|---|-----------|----------------|-----------|-------|
| 2.1 | Run `uv run trinity` from project root | Trinity TUI launches without traceback | | |
| 2.2 | Observe provider readiness panel on startup | Each configured provider shows a readiness status: `READY`, `AUTH_REQUIRED`, `MODEL_LOADING`, `CLI_BANNER_ONLY`, or `UNKNOWN_NOT_READY` | | |
| 2.3 | With all providers authenticated | All providers show `READY` | | |
| 2.4 | With one provider not authenticated (e.g. run `gemini` without auth) | That provider shows `AUTH_REQUIRED` with clear action hint (e.g. `Run: gemini auth login`) | | |
| 2.5 | With `strict_provider_readiness = true` in config and at least one provider not ready | Workflow shows `FAILED` state with message indicating which provider failed and why | | |
| 2.6 | With `strict_provider_readiness = false` / `allow_degraded_agent_set = true` and some providers not ready | Only `READY` providers proceed; unready providers are excluded with a warning | | |
| 2.7 | With zero providers ready | Workflow transitions to `FAILED`; TUI shows clear message: no agents available, with action hints for each provider | | |
| 2.8 | Status display shows provider model | TUI shows model name next to each ready provider (e.g. `claude READY opus[1m]`) | | |

---

## 3. Workflow Scenarios

### Scenario 1: Single Agent (Claude Only)

**Setup**: Configure `trinity.config` with only the `claude` agent enabled. Authenticate Claude.

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|----------------|-----------|-------|
| 1.1 | Enter a design prompt, e.g. `Design a REST API for a task queue` | Workflow transitions: `PREFLIGHT` -> `DELIBERATING` | | |
| 1.2 | Observe deliberation progress | Claude produces a structured opinion; TUI shows round progress | | |
| 1.3 | After deliberation completes | Workflow transitions to `BLUEPRINT_READY`; a `Blueprint` is stored with title, summary, architecture components, acceptance criteria | | |
| 1.4 | Blueprint content check | Blueprint has at least one `ArchitectureComponent` with name, responsibility, and owner_agent = `claude` | | |
| 1.5 | If open questions are generated | Workflow transitions to `NEEDS_USER_DECISION` (not just `BLUEPRINT_READY`) | | |
| 1.6 | No open questions case | Workflow shows blueprint summary and offers execution or done | | |
| 1.7 | `/status` command | Shows: session id, `BLUEPRINT_READY` state, 1 active agent, blueprint title | | |

### Scenario 2: All 3 Agents Authenticated

**Setup**: Configure `trinity.config` with claude, codex, and gemini all enabled and authenticated.

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|----------------|-----------|-------|
| 2.1 | Enter a design prompt | Workflow transitions: `PREFLIGHT` -> `DELIBERATING` with 3 active agents | | |
| 2.2 | Round 1 (proposal) | Each agent submits a structured proposal; TUI shows all 3 opinions collected | | |
| 2.3 | Round 2+ (critique/synthesis) | Agents critique each other's proposals and/or produce synthesis | | |
| 2.4 | Agents cast structured votes | At least some votes appear as `APPROVE`, `APPROVE_WITH_CHANGES`, `BLOCKED_BY_QUESTION`, or `REJECT` | | |
| 2.5 | Consensus reached (majority approve) | `StructuredConsensusResult.reached = true`; workflow transitions to `BLUEPRINT_READY` | | |
| 2.6 | Consensus not reached | Either more rounds continue (up to max_deliberation_rounds), or open questions are generated leading to `NEEDS_USER_DECISION` | | |
| 2.7 | Open questions generated | Questions have id, text, options, recommended_option, raised_by list, and rationale | | |
| 2.8 | `/status` command | Shows: round number, active agents, vote counts (if any), pending questions count | | |

### Scenario 3: User Decision Loop

**Setup**: Any agent count; prompt that triggers open questions (e.g. ambiguous design choices).

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|----------------|-----------|-------|
| 3.1 | Deliberation produces open questions | Workflow transitions to `NEEDS_USER_DECISION`; TUI displays questions with numbered options and recommendation | | |
| 3.2 | Run `/answer <question-id\|index\|next> <answer>` | Answer is treated as a response to the selected pending question, not a new goal; `DecisionRecord` is created with `decided_by = "user"` | | |
| 3.3 | Run `/questions --select --all` | Direction-key wizard records option answers and free-text answers for pending questions | | |
| 3.4 | After all blocking answers | Workflow transitions back to `DELIBERATING`; the decisions are injected into the next round prompt | | |
| 3.5 | Decision recorded in shared context | shared.md `## Decisions` section contains the new decision with id, question_id, decision text, and rationale | | |
| 3.6 | `/questions` command | Lists all pending (unanswered) questions with their options and actionable `/answer` examples | | |
| 3.7 | `/decisions` command | Lists all recorded decisions so far | | |
| 3.8 | Answer all blocking questions | Workflow eventually reaches `BLUEPRINT_READY` or `DONE` | | |
| 3.9 | Non-blocking question remaining | Workflow can still proceed past `NEEDS_USER_DECISION` even with non-blocking questions unanswered | | |

### Scenario 4: Execution Dispatch

**Setup**: Reach `BLUEPRINT_READY` state (via Scenario 1 or 2). Config should have `workflow.execution.enabled = true`.

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|----------------|-----------|-------|
| 4.1 | Approve execution (or auto-proceed if `require_user_approval_before_execution = false`) | Blueprint is decomposed into N work packages where N = number of active agents | | |
| 4.2 | Work package structure | Each `WorkPackage` has: id, title, owner_agent, objective, scope, out_of_scope, acceptance_criteria, status = `PENDING` | | |
| 4.3 | Workflow transitions to `EXECUTING` | TUI shows package list with agent assignments | | |
| 4.4 | Package dispatch | Each package is sent to its owner agent; status changes to `RUNNING` | | |
| 4.5 | Results collected | Each agent returns an `ExecutionResult` with summary, files_changed, decisions_made, blockers | | |
| 4.6 | Results recorded | shared.md `## Task Results` section contains all execution results | | |
| 4.7 | Package failure | If an agent returns `FAILED` or `BLOCKED`, workflow reflects this in the package status and TUI | | |
| 4.8 | All packages complete | Workflow transitions to `REVIEWING` or `DONE` | | |
| 4.9 | `/status` shows work package statuses | Each package shows: id, owner, status (PENDING/RUNNING/DONE/FAILED) | | |

### Scenario 5: Lifecycle Rotation

**Setup**: Any configuration. This tests context threshold monitoring and session rotation.

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|----------------|-----------|-------|
| 5.1 | Monitor context usage display | TUI or `/status` shows context usage per agent (e.g. `claude: 45,000/200,000 (22.5%)`) | | |
| 5.2 | Trigger high context usage (multiple rounds or large prompts) | Context ratio approaches `context_rotate_threshold` (default 0.60 = 60%) | | |
| 5.3 | Rotation triggered before next prompt | `LifecycleGuard` detects ratio >= threshold; current session is summarized | | |
| 5.4 | Summary produced | Agent produces a session summary covering: completed work, in-progress work, next steps, decisions | | |
| 5.5 | shared.md updated | Session summary is recorded in shared context | | |
| 5.6 | New session starts | Agent session is replaced (pane restarted or re-initialized); continuation prompt is injected containing previous summary + current blueprint + open packages | | |
| 5.7 | Workflow continues after rotation | New session picks up where it left off; workflow state is preserved (same session id, same state) | | |
| 5.8 | Rotation during execution | Rotation can occur between work packages; in-progress package status is preserved | | |
| 5.9 | Token usage not stuck at 0 | After at least one real agent response, `total_tokens_used > 0` | | |

---

## 4. TUI and Command Verification

| # | Command / Feature | Expected Result | Pass/Fail | Notes |
|---|-------------------|----------------|-----------|-------|
| 4.1 | `/status` | Shows: workflow state, session id, round number, active agents, pending questions, blueprint status, work package summary | | |
| 4.2 | `/questions` | Lists pending open questions with options | | |
| 4.3 | `/decisions` | Lists recorded decisions with who decided and rationale | | |
| 4.4 | `/workflow` | Shows full workflow state machine: current state, available transitions, session history | | |
| 4.5 | Prompt input when `state = NEEDS_USER_DECISION` | Plain text is not auto-recorded; TUI instructs the user to use `/answer` or `/questions --select` | | |
| 4.6 | Prompt input when `state = IDLE` | Input starts a new workflow (goal) | | |
| 4.7 | Provider status panel | Shows each provider name, readiness state, model, and action hint if not ready | | |
| 4.8 | Graceful shutdown (Ctrl+C) | TUI exits cleanly; tmux session is killed; workflow state is persisted if `persist_workflow_state = true` | | |
| 4.9 | Restart after shutdown | `uv run trinity` restores previous workflow state from `.trinity/workflow/session.json` | | |

---

## 5. Persistence and Recovery

| # | Test Step | Expected Result | Pass/Fail | Notes |
|---|-----------|----------------|-----------|-------|
| 5.1 | Complete a workflow to `BLUEPRINT_READY`, then Ctrl+C | `.trinity/workflow/session.json` exists with correct state | | |
| 5.2 | Restart Trinity | Previous session is restored; TUI shows `BLUEPRINT_READY` with the same blueprint | | |
| 5.3 | Resume from `NEEDS_USER_DECISION` | Pending questions are preserved; user can answer them after restart | | |
| 5.4 | Resume from `EXECUTING` | Work package statuses are preserved; completed packages remain `DONE`, pending ones can be dispatched | | |
| 5.5 | Event log written | `.trinity/workflow/events.jsonl` contains state transitions with timestamps | | |

---

## 6. Error and Edge Cases

| # | Test Step | Expected Result | Pass/Fail | Notes |
|---|-----------|----------------|-----------|-------|
| 6.1 | Agent pane crashes mid-deliberation | `LifecycleGuard` detects `PROCESS_DEAD`; workflow either retries or marks agent unavailable and continues with remaining agents | | |
| 6.2 | All agent panes crash | Workflow transitions to `FAILED` with error details | | |
| 6.3 | Agent response is empty or invalid | Response is classified as `EMPTY` or `INVALID`; not recorded as opinion; does not corrupt consensus | | |
| 6.4 | Agent response contains auth/UI noise | Response is classified as `AUTH_REQUIRED` or `CLI_NOISE` via `ResponseValidator`; not recorded as opinion | | |
| 6.5 | Deliberation reaches max rounds without consensus | Workflow does not hang; either transitions to `NEEDS_USER_DECISION` with remaining disagreements, or `FAILED` with a summary | | |
| 6.6 | Invalid state transition attempt (e.g. `DONE` -> `EXECUTING`) | `WorkflowEngine` raises `ValueError`; workflow does not corrupt | | |
| 6.7 | Config with `workflow_mode = "autonomous"` | Workflow does not block on `NEEDS_USER_DECISION` for non-blocking questions; makes reasonable agent-local decisions | | |
| 6.8 | `tmux kill-server` during execution | Trinity detects tmux unavailable on next tick; reports error cleanly | | |

---

## 7. Result Recording

| Field | Value |
|-------|-------|
| **Date** | |
| **Tester** | |
| **Environment** | (e.g. WSL2 Ubuntu 22.04, macOS 15.5, native Linux) |
| **tmux version** | |
| **Python version** | |
| **uv version** | |
| **Trinity version** | |
| **Agents configured** | (e.g. claude, codex, gemini) |
| **Agents authenticated** | (which ones were READY at preflight) |
| **Config overrides** | (any non-default settings used) |
| | |
| **Scenario 1 (Single Agent)** | PASS / FAIL / SKIP |
| **Scenario 2 (All 3 Agents)** | PASS / FAIL / SKIP |
| **Scenario 3 (User Decision Loop)** | PASS / FAIL / SKIP |
| **Scenario 4 (Execution Dispatch)** | PASS / FAIL / SKIP |
| **Scenario 5 (Lifecycle Rotation)** | PASS / FAIL / SKIP |
| **TUI and Commands** | PASS / FAIL / SKIP |
| **Persistence and Recovery** | PASS / FAIL / SKIP |
| **Error and Edge Cases** | PASS / FAIL / SKIP |
| | |
| **Overall Result** | PASS / FAIL / PARTIAL |
| **Notes** | |

---

## 8. Known Limitations (v0.7.0)

- Subagent delegation tracking relies on parent agent self-reporting; Trinity does not directly control provider-internal subagent calls.
- Gemini CLI completion detection may use idle timeout fallback (up to 20s) when explicit markers are not output.
- Context token counting for Codex depends on session file polling; counts may lag behind actual usage.
- `strict_provider_readiness = true` (default) will block workflow if any single provider is not ready. Use `allow_degraded_agent_set = true` for degraded-mode testing.

---

## 9. Quick Reference: State Transitions

```
IDLE --> PREFLIGHT --> DELIBERATING --> BLUEPRINT_READY --> EXECUTING --> REVIEWING --> DONE
                      |                    |                   |              |
                      |                    |                   |              +--> NEEDS_USER_DECISION
                      |                    |                   |
                      +--> NEEDS_USER_DECISION <--+            +--> FAILED
                      |                            |
                      +--> FAILED                  +--> DONE
```

Any non-terminal state can transition to `FAILED` on unrecoverable error.
`NEEDS_USER_DECISION` always transitions back to `DELIBERATING` after user answers.
`BLUEPRINT_READY` can transition directly to `DONE` if execution is not required (design-only).
