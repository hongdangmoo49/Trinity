# Target Workspace Context End-to-End

## Problem

Trinity persists a selected target workspace and uses it for execution, review,
and Textual deliberation orchestrator construction, but the workspace is not
explicitly carried through every planning prompt and central synthesis payload.
That leaves planning agents and the central synthesizer free to reason as if
the Trinity control repository is the project under design, even when the user
selected a separate workspace for the deliverable.

## Scope

Owned by this change:

- Deliberation round prompts must include the selected target workspace when one
  exists.
- Question-answer continuations must restate the selected target workspace.
- Blueprint follow-up prompts must restate the selected target workspace.
- Central synthesis input and provider-backed synthesis JSON payloads must carry
  target workspace context in a stable schema field.
- Work-package and final review prompts must state the selected target
  workspace.
- Plain TUI deliberation orchestrator creation must pass the persisted target
  workspace when one is selected.
- Focused tests must cover the prompt and orchestration propagation points.

Out of scope:

- Changing target workspace selection UX, session goal text, or visible prompt
  labels.
- Changing execution authority, write guards, workspace isolation, or provider
  launch cwd policy.
- Version bumps, broad refactors, or pushes.

## Design

### Canonical Context String

Add a small helper in `WorkflowEngine` that renders target workspace context for
engine-owned continuation prompts. When no workspace is selected, it returns an
empty string so existing prompt text remains unchanged.

The prompt wording should say that implementation artifacts and project file
references are scoped to the selected target workspace. It should not imply
that read-only planning calls may write files.

### Deliberation Round Prompts

Extend `DeliberationProtocol` with an optional `target_workspace: Path | None`.
When present, `_build_round_prompt()` prepends/appends a concise target
workspace context block to both first-round and later-round prompts before
structured-output instructions are appended. This keeps the output contract at
the end while ensuring every agent sees the workspace path.

`TrinityOrchestrator` will pass its resolved `target_workspace` into the
protocol.

### Central Synthesis Payload

Extend `SynthesisInput` with `target_workspace: str = ""`. `DeliberationProtocol`
will populate it from its target workspace for every round. `SynthesisInput`
remains backward compatible because the field has a default.

`ModelBackedSynthesisAgent._build_prompt()` will add both:

- `target_workspace`: the raw path string or `null`.
- A rule telling the central agent to treat relative files and project artifact
  references as relative to the target workspace when present.

`SynthesisResult.to_dict()` does not need a top-level schema change for this
task because it serializes the result, not the input payload. The payload sent
to the central provider is the central synthesis schema surface that needs the
explicit context.

### Review Prompts

Extend `ReviewExecutionProtocol` with `target_workspace: Path | None` and pass it
from `TrinityOrchestrator`. Include a target workspace block in work-package and
final review prompts when available. Review access remains read-only.

### Plain TUI Orchestrator Creation

`TextualWorkflowController` already passes `target_workspace` into deliberation.
Plain `trinity.tui.session.TrinitySession._run_deliberation()` currently does
not. Pass the persisted workflow target and control-repo confirmation flag into
`TrinityOrchestrator` there, without changing the visible "Deliberation
Starting" panel or workflow goal text.

## Test Plan

- Add workflow engine tests for decision-answer continuation and blueprint
  follow-up prompts including the selected target workspace.
- Add deliberation protocol tests for round prompt and `SynthesisInput`
  propagation.
- Add model-backed synthesis prompt tests for the central JSON payload
  containing `target_workspace`.
- Add review execution protocol tests for work-package and final review prompts
  containing the target workspace.
- Add or extend plain TUI session tests so `_run_deliberation()` passes the
  selected target workspace into `TrinityOrchestrator`.

