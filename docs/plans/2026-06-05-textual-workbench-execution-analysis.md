# Textual Workbench Execution Wiring Analysis

- Date: 2026-06-05
- Branch: `feature/textual-workbench-execution-analysis`
- Status: analysis
- Scope: Textual workbench에서 첫 프롬프트, workspace 선택, Nexus follow-up, provider 실행 상태가 실제 workflow/orchestrator 실행으로 이어지지 않는 문제를 분석한다.

## Summary

현재 Textual workbench는 화면 전환과 read-only snapshot 렌더링은 구현되어 있지만, 기존 plain TUI가 가지고 있는 workflow controller와 deliberation runner가 연결되어 있지 않다.

핵심 문제는 다음 네 가지다.

1. Start Screen의 `Choose now`는 메시지를 발행하지만 app-level handler가 없어 동작하지 않는다.
2. Execute preflight의 directory tree가 Trinity control repo를 root로 삼아 상위 workspace를 트리에서 선택할 수 없다.
3. 첫 프롬프트 제출은 `WorkflowEngine.start()`와 `TrinityOrchestrator.ask()`를 호출하지 않고 임시 snapshot만 만든다.
4. Nexus follow-up과 question answer 이벤트는 app-level handler에서 `event.stop()`만 하고 끝나므로 workflow 상태, provider 상태, synthesis가 갱신되지 않는다.

따라서 이번 수정은 CSS나 panel 배치 문제가 아니라 Textual UI와 기존 workflow/orchestrator runtime 사이의 실행 연결을 추가하는 작업이다.

## Current Runtime Path

`uv run trinity`는 `.trinity/trinity.config`가 있는 프로젝트에서 Textual이 사용 가능하면 `TrinityTextualApp`을 실행한다.

```text
trinity.cli._run_interactive_tui()
  -> trinity.textual_app.runtime.resolve_tui_runtime()
  -> trinity.textual_app.app.run_textual_app()
  -> TrinityTextualApp
```

기존 plain TUI는 아래 경로로 실제 provider 실행을 시작한다.

```text
InteractiveSession._handle_user_text()
  -> WorkflowEngine.handle_user_input()
  -> WorkflowInputAction(should_deliberate=True)
  -> InteractiveSession._run_deliberation()
  -> TrinityOrchestrator.ask()
  -> DeliberationProtocol.run()
  -> provider events + persisted workflow result
```

Textual workbench에는 위 흐름과 대응되는 controller가 아직 없다. 현재 Textual app은 snapshot을 만들고 화면에 적용하는 데서 멈춘다.

## Symptom 1: First Page Buttons Do Not Perform Useful Actions

### Observed

첫 페이지에는 두 버튼이 있다.

- `Choose now`
- `Plan first`

사용자는 두 버튼 모두 의미 있는 동작을 하지 않는 것으로 느낀다.

### Code Path

`StartScreen.on_button_pressed()`는 두 버튼을 구분한다.

- `plan-first`: composer 내용을 `StartScreen.Submitted`로 발행한다.
- `choose-workspace`: `StartScreen.WorkspaceRequested`를 발행한다.

Relevant files:

- `src/trinity/textual_app/screens/start.py`
- `src/trinity/textual_app/app.py`

### Root Cause

`Choose now`의 경우 `StartScreen.WorkspaceRequested`를 처리하는 `TrinityTextualApp` handler가 없다. 그래서 버튼 클릭 이벤트는 screen 안에서 메시지로 변환되지만 app이 아무 작업도 하지 않는다.

`Plan first`는 빈 프롬프트가 아니면 Nexus 화면으로 이동할 수 있지만, 실제 provider 실행을 시작하지 않는다. `TrinityTextualApp.on_start_screen_submitted()`는 다음만 수행한다.

1. `initial_prompt` 저장
2. `workspace_candidate` 저장
3. `NexusSnapshotAdapter.new_session_snapshot()` 호출
4. Nexus 화면에 snapshot 적용
5. `switch_to("nexus")`

여기서 생성되는 snapshot은 `state="preflight"`, provider status는 기본 `Queued`인 in-memory projection이다. workflow state machine이나 orchestrator는 호출되지 않는다.

### Expected Behavior

`Choose now`:

- target workspace candidate를 선택하는 modal을 열어야 한다.
- Start 단계의 workspace는 최종 execute 대상이 아니라 candidate여야 한다.
- 선택 후 Start Screen의 label이 갱신되어야 한다.

`Plan first`:

- 첫 프롬프트를 현재 workflow의 goal로 등록해야 한다.
- Nexus 화면으로 이동한 뒤 provider panels가 `Running` 또는 readiness/error 상태로 갱신되어야 한다.
- provider 응답과 central synthesis가 완료되면 `Ready`, `needs_user_decision`, `blueprint_ready` 같은 실제 workflow snapshot으로 갱신되어야 한다.

## Symptom 2: Execute Preflight Cannot Select a Parent Workspace

### Observed

Nexus 화면의 `Execute`를 누르면 `Execute Preflight` modal은 뜨지만, directory tree에서 Trinity 작업 폴더보다 상위 경로를 선택할 수 없다.

### Code Path

`TrinityTextualApp.on_nexus_screen_execute_requested()` creates `WorkspacePicker` with:

```python
WorkspacePicker(
    candidate=self.workspace_candidate,
    snapshot=snapshot,
    cwd=self.config.project_dir,
)
```

`WorkspacePicker.compose()` renders:

```python
DirectoryTree(self.cwd, id="workspace-directory-tree")
```

Relevant files:

- `src/trinity/textual_app/app.py`
- `src/trinity/textual_app/widgets/workspace_picker.py`

### Root Cause

`DirectoryTree` root is hard-bound to `self.config.project_dir`, which is the Trinity control repo. A Textual `DirectoryTree` cannot navigate above its root, so `/home/user/workspace` or sibling project directories are inaccessible from the tree.

The text input can technically accept an arbitrary path, but the visible picker contradicts the target workspace boundary design. The earlier target workspace boundary plan says implementation output should normally go outside the Trinity control repo.

### Expected Behavior

The picker should make the recommended target path outside the Trinity repo selectable.

Recommended fixes:

1. Use a broader tree root such as `config.project_dir.parent`, a configured workspace root, or the user's home/workspace root.
2. Preserve the input field for absolute paths.
3. Show the recommended default target workspace derived from the blueprint title or goal.
4. Keep the guard that warns before writing inside the Trinity control repo.

## Symptom 3: First Prompt Does Not Start Provider Work

### Observed

첫 페이지에서 프롬프트를 입력하고 Enter를 누르면 Nexus 화면으로 이동하지만 provider cards가 계속 `Queued`로 남는다. 사용자가 기대하는 동작은 다음과 같다.

1. 입력한 프롬프트가 Central Agent goal로 표시된다.
2. Claude, Codex, Antigravity가 응답 생성 중임을 보여준다.
3. provider 응답과 synthesis가 UI에 반영된다.

### Code Path

Current Textual path:

```text
PromptComposer.Submitted
  -> StartScreen._submit()
  -> StartScreen.Submitted
  -> TrinityTextualApp.on_start_screen_submitted()
  -> NexusSnapshotAdapter.new_session_snapshot()
  -> NexusScreen.apply_snapshot()
```

Expected runtime path from plain TUI:

```text
WorkflowEngine.start(goal, active_agents)
  -> workflow state DELIBERATING
  -> TrinityOrchestrator.ask(goal)
  -> TUIEventBus events
  -> WorkflowEngine.mark_deliberation_result(result)
  -> snapshot from persisted workflow session + recent events
```

### Root Cause

`NexusSnapshotAdapter.new_session_snapshot()` intentionally creates a fresh in-memory snapshot to avoid leaking a previous session. That was correct for session isolation, but it is not a workflow start operation.

No code currently:

- instantiates `WorkflowEngine` in the Textual app,
- archives/restores sessions intentionally,
- calls `WorkflowEngine.handle_user_input()` or `WorkflowEngine.start()`,
- creates `TrinityOrchestrator`,
- attaches a `TUIEventBus`,
- runs `orchestrator.ask()` in a background task/thread,
- consumes provider events into `NexusScreen.update_provider()`,
- calls `WorkflowEngine.mark_deliberation_result()`,
- reloads a final `WorkflowNexusSnapshot`.

Therefore provider panels remain in their initial `Queued` state.

### Expected Behavior

Textual needs a controller equivalent to the plain TUI's deliberation runner, adapted for Textual's async app model.
