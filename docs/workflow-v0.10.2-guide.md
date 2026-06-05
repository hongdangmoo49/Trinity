# Trinity v0.10.2 Workflow and Runtime Guide

작성일: 2026-06-05

이 문서는 Trinity `0.10.2` 기준의 실제 워크플로우와 런타임 동작 방식을 정리한다.
기준 코드는 `pyproject.toml`, `src/trinity/cli.py`, `src/trinity/orchestrator.py`,
`src/trinity/workflow/engine.py`, `src/trinity/workflow/execution.py`,
`src/trinity/textual_app/workflow_controller.py`이다.

## 핵심 요약

Trinity는 Claude Code, Codex, Antigravity CLI를 하나의 workflow로 묶는
멀티 에이전트 오케스트레이터다. 사용자의 요구사항은 먼저 planning 단계에서
라운드 기반 토론과 central synthesis를 거쳐 blueprint로 정리된다. 실제 파일
수정은 planning이 끝난 뒤 사용자가 `Execute`를 선택하고 target workspace
preflight를 통과해야 시작된다.

기본 UI는 Textual Workbench이며, 기존 Rich/prompt_toolkit TUI는 fallback으로
남아 있다. 기본 provider transport는 one-shot CLI invocation이고, tmux
transport는 legacy/debug 경로다.

## 진입점

| 진입점 | 실제 동작 |
| :--- | :--- |
| `trinity` | `.trinity/trinity.config`를 읽고 Textual Workbench를 실행한다. Textual을 사용할 수 없거나 `TRINITY_TUI=plain`이면 plain TUI로 fallback한다. |
| `trinity --plain` | 기존 Rich/prompt_toolkit 기반 plain TUI를 강제로 실행한다. |
| `trinity ask "..."` | 대화형 화면 없이 one-shot deliberation을 실행한다. 기본 transport는 one-shot이다. |
| `trinity init` | provider CLI 탐지, 모델/역할/예산 선택, `.trinity/trinity.config` 저장을 수행한다. |
| `trinity bootstrap` | 현재 터미널에서 provider CLI의 auth/trust 초기 설정을 순차 확인한다. |
| `trinity bootstrap --legacy-tmux` | legacy tmux bootstrap 세션을 실행한다. |

## 저장되는 상태

| 경로 | 내용 |
| :--- | :--- |
| `.trinity/trinity.config` | provider, model, transport, readiness, synthesis, context, UI 설정 |
| `.trinity/shared.md` | 에이전트가 공유하는 ledger와 요약 context |
| `.trinity/workflow/session.json` | 현재 workflow 상태, 질문, 결정, blueprint, work package, 실행 결과 |
| `.trinity/workflow/events.jsonl` | workflow state transition과 사용자 결정 이벤트 |
| `.trinity/workflow/history/` | 이전 active workflow session archive |
| `.trinity/responses/` | provider별 raw/clean response artifact |
| `.trinity/execution/` | work package 실행 artifact |
| `.trinity/logs/` | orchestrator/runtime 로그 |

## 상태 머신

`WorkflowEngine`은 사용자의 일반 입력을 현재 상태에 맞게 라우팅한다.

```text
IDLE
  -> PREFLIGHT
  -> DELIBERATING
  -> NEEDS_USER_DECISION
  -> DELIBERATING
  -> BLUEPRINT_READY
  -> EXECUTING
  -> REVIEWING
  -> DONE
```

실패하면 어느 단계에서든 `FAILED`로 전이될 수 있다.

주요 규칙은 다음과 같다.

- 새 목표는 `WorkflowEngine.start()`에서 새 workflow session으로 저장되고 곧바로
  `DELIBERATING` 상태가 된다.
- central synthesis가 blocking question을 만들면 `NEEDS_USER_DECISION`으로 멈춘다.
- 사용자의 `/answer` 또는 Textual 질문 답변은 `DecisionRecord`로 저장되고,
  남은 질문이 없으면 decision continuation prompt로 다시 deliberation을 실행한다.
- blueprint가 준비되면 `BLUEPRINT_READY`가 된다. 이 상태에서 일반 follow-up은
  blueprint 보강으로, 실행 의도는 execution 준비로 라우팅된다.
- target workspace가 없으면 실행은 시작되지 않는다.
- 실행 결과가 모두 끝나면 peer review package가 계획되고 `REVIEWING`으로 전이된다.

## Planning 흐름

Textual Workbench의 첫 prompt는 다음 경로를 탄다.

```text
Start Screen
  -> TextualWorkflowController.start_prompt()
  -> WorkflowEngine.start()
  -> background thread
  -> TrinityOrchestrator.ask()
  -> ProviderReadinessGate
  -> DeliberationProtocol.run()
  -> provider one-shot invocations
  -> ModelBackedSynthesisAgent or HeuristicSynthesisAgent
  -> WorkflowEngine.mark_deliberation_result()
  -> NexusSnapshotAdapter
  -> Nexus Screen update
```

Planning 단계에서 provider는 기본적으로 read-only request로 호출된다. 이 단계의
목표는 코드를 수정하는 것이 아니라 요구사항을 분석하고, open question과 blueprint를
만드는 것이다.

## Provider 호출 방식

Provider 호출은 `PromptRequest`와 `ProviderTurnResult`로 정규화된다.

| Provider | 호출 방식 | 출력 처리 |
| :--- | :--- | :--- |
| Claude Code | `claude -p --output-format json` | JSON의 `result`/`content`와 usage를 파싱한다. |
| Codex | `codex exec --json --ephemeral --skip-git-repo-check --sandbox ... --cd ...` | JSONL event에서 `agent_message`, usage, tool activity를 파싱한다. |
| Antigravity CLI | `agy --print --print-timeout=...` | plain stdout을 응답으로 사용한다. read-only 요청에는 `--sandbox`를 붙인다. |

응답은 auth error, model loading, timeout, prompt echo, cli noise, empty output 같은
상태로 분류된다. raw/clean artifact를 남기기 때문에 provider UI가 섞여 들어온
경우에도 원문과 정제본을 추적할 수 있다.
Antigravity가 exit code 0으로 빈 stdout을 반환하면 `empty_response` 진단과 함께 raw
artifact에 원인을 남긴다.

## Execution 흐름

Execution은 planning과 분리되어 있다. Textual Workbench에서는 `Execute`를 누른 뒤
workspace picker와 preflight를 통과해야 한다.

```text
Nexus Execute
  -> WorkspacePicker preflight
  -> WorkflowEngine.set_target_workspace()
  -> WorkflowEngine.enable_execution_for_current_blueprint()
  -> WorkflowEngine.begin_execution()
  -> TrinityOrchestrator.execute_work_packages()
  -> ExecutionProtocol.run()
  -> dependency-safe batch planning
  -> provider workspace-write invocation
  -> WorkflowEngine.record_execution_results()
  -> REVIEWING or NEEDS_USER_DECISION or FAILED
```

`ExecutionProtocol`은 실행 전에 다음 boundary를 확인한다.

- target workspace가 반드시 있어야 한다.
- target workspace가 Trinity control repo 내부이면 명시적 확인이 필요하다.
- agent launch cwd가 control repo 내부인데 확인이 없으면 provider write를 거부한다.
- dependency가 끝나지 않은 work package는 실행하지 않는다.
- 같은 workspace를 provider가 관리하며 파일 소유권이 겹치는 package는 병렬 실행하지 않는다.

## Textual Workbench의 역할

Textual 앱은 별도 workflow 엔진이 아니다. `TextualWorkflowController`가 기존
`WorkflowEngine`과 `TrinityOrchestrator`를 background thread에서 실행하고,
`TUIEventBus` 이벤트와 persisted workflow state를 snapshot으로 합쳐 화면에 보여준다.

화면 역할은 다음과 같다.

| 화면 | 역할 |
| :--- | :--- |
| Start | 첫 요구사항 작성, 선택적 workspace candidate 지정 |
| Nexus | provider 상태, central synthesis, 질문, decision, blueprint, package 상태 표시 |
| Provider Inspector | provider raw output을 탭 modal로 확인 |
| Execute Preflight | target workspace 선택, 경로/git/write 가능성 확인, 필요한 폴더 생성 |
| Execution Matrix | work package table과 execution log 표시 |
| Settings | theme, density, motion, Unicode preference 저장 |

## Plain TUI와 legacy tmux

plain TUI는 `InteractiveSession`이 사용자 입력을 받고 `WorkflowEngine`과
`TrinityOrchestrator`를 직접 호출한다. slash command는 `/status`, `/context`,
`/questions`, `/answer`, `/target`, `/execute`, `/resume` 같은 workflow 조작에 사용된다.

tmux transport는 기본 경로가 아니며 legacy/debug 목적으로 유지된다. `transport_mode =
"tmux"` 또는 관련 CLI 옵션을 사용할 때만 pane-backed interactive agent를 만든다.

## 운영상 주의점

- provider CLI의 auth/trust 상태는 unit test로 검증할 수 없다. 실제 환경에서는
  `trinity bootstrap`과 provider smoke가 필요하다.
- 실행 전 target workspace는 control repo와 분리하는 것이 기본 원칙이다.
- `.trinity/workflow/session.json`과 `.trinity/workflow/events.jsonl`이 현재 workflow
  truth source다.
- Textual은 UI projection이고, 권한 판단은 workflow/execution protocol 계층에서 한다.
- `src/trinity/bridge`는 L2 bridge 예시/도메인 모듈로 존재하지만 현재 CLI/TUI의
  주 orchestration 경로에는 직접 연결되어 있지 않다.
