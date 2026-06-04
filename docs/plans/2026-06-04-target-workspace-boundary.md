# Target Workspace Boundary

Date: 2026-06-04
Status: proposed

## Problem

Trinity currently uses the same `project_dir` for two different purposes:

- running Trinity itself
- giving provider agents a workspace for user-requested implementation

That makes the Trinity repository both the orchestrator codebase and the target
project. When a user asks for a product such as "레이어2 에 속하는 체인들 간
브릿지 경로를 빨리 찾아주는 봇", generated work packages can instruct agents
to edit `src/` and `tests/`. With `workspace_mode = "inplace"`, those writes land
inside the Trinity repository itself.

This violates the repository boundary. The Trinity project should contain only
Trinity runtime/orchestration code, tests, docs, and runtime metadata. User
product artifacts must be written to an explicit target workspace.

## Observed Incident

The prompt:

> 레이어2 에 속하는 체인들 간 브릿지 경로를 빨리 찾아주는 봇을 개발하고 싶다. 설계해라

was treated as executable implementation because it contained "개발하고 싶다",
even though the direct instruction was "설계해라". After blueprint consensus,
Trinity generated executable work packages and provider agents modified Trinity
source files under:

- `src/trinity/bridge/`
- `tests/test_bridge_engine.py`

Runtime records were also written under `.trinity/`, which is acceptable as
Trinity local state.

## Decision

Separate the Trinity control repository from the user target workspace.

Terminology:

- Control repo: the repository where Trinity is installed or developed.
- Target workspace: the project directory where provider agents may create or
  modify user product files.
- Runtime state: Trinity's own `.trinity/` session, event, response, execution,
  and history files.

Trinity may write runtime state under the control repo's `.trinity/`. Trinity
must not write user product files into the control repo unless the user
explicitly selects the control repo as the target workspace after a warning.

## Target Workflow

Design-only request:

1. User asks for design, planning, or architecture.
2. Trinity runs deliberation and records blueprint state.
3. Trinity stops at `blueprint_ready`.
4. No target workspace is required.
5. No provider receives `workspace-write` execution.

Implementation request:

1. User asks to implement an approved blueprint.
2. Trinity checks whether a target workspace is configured.
3. If not configured, Trinity asks where to create or use the project.
4. Provider agents execute only inside the selected target workspace.
5. Runtime state remains under Trinity `.trinity/`.

## Target Workspace Selection

When implementation is requested and no target workspace exists, the terminal UI
should present choices:

1. Create a new project directory under the user's workspace root.
2. Use an existing project directory.
3. Use the current directory.
4. Cancel implementation.

The current directory option must show a warning when it is the Trinity control
repo:

> 현재 경로는 Trinity 제어 저장소입니다. 여기에 사용자 프로젝트 파일을 만들면
> Trinity 코드와 산출물이 섞입니다. 그래도 계속할까요?

The recommended default is creating a new target directory derived from the
blueprint title, for example:

`/home/zaemi/workspace/l2-bridge-route-bot`

## Intent Rules

Execution intent must be conservative.

Design intent must override aspirational implementation wording. For example:

- "개발하고 싶다. 설계해라" => design only
- "만들고 싶다. 구조를 잡아라" => design only
- "구현하지 말고 설계만 해라" => design only
- "이 설계대로 구현해라" => implementation
- "개발 시작해라" => implementation

Only explicit implementation commands should enable executable work packages.

## Safety Rules

- Do not run provider `workspace-write` requests in the Trinity control repo by
  default.
- Refuse implementation if the target workspace is missing.
- Persist the selected target workspace in workflow state so resume uses the
  same directory.
- Include target workspace path in `/workflow`, `/status`, and execution start
  panels.
- If provider workspaces use git worktrees, create them from the target
  workspace, not from the Trinity control repo.
- `.trinity/responses`, `.trinity/execution`, `.trinity/workflow`, and
  `.trinity/history` remain runtime metadata and are not user product files.

## Cleanup Policy

If provider agents accidentally modify the Trinity control repo with user
product artifacts:

1. Stop or cancel active provider processes.
2. Inspect `git status --short`.
3. Revert only generated product artifact changes.
4. Keep Trinity runtime logs unless the user explicitly asks to purge runtime
   state.
5. Document the incident and update boundary safeguards.

For the 2026-06-04 incident, generated product artifact changes are the
uncommitted edits under:

- `src/trinity/bridge/`
- `tests/test_bridge_engine.py`

Trinity workflow fixes and documentation changes are not product artifacts.

## Implementation Tasks

1. Add `target_workspace` to workflow session state.
2. Add target workspace selection UI before execution.
3. Make execution intent conservative for Korean and English design-only
   phrasing.
4. Ensure `ExecutionProtocol` receives target workspace paths for provider
   launch contexts.
5. Add guardrails that block `workspace-write` into the control repo unless
   explicitly confirmed.
6. Add tests for design-only prompts containing aspirational product wording.
7. Add tests that implementation without target workspace asks for a target path.
8. Add tests that provider writes go to target workspace worktrees.

## Acceptance Criteria

- A design-only prompt does not create or modify files outside `.trinity/`.
- An implementation prompt without a target workspace asks the user for a
  destination.
- The default target workspace is outside the Trinity control repo.
- Provider execution writes only inside the selected target workspace.
- The Trinity control repo remains clean after designing a user product.
