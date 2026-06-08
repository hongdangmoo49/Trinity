# Trinity v0.12.0 Workflow and Runtime Guide

작성일: 2026-06-05

이 문서는 Trinity `0.12.0` 기준의 실제 워크플로우와 런타임 동작 방식을 정리한다.
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
- 실행 후 `REVIEWING`/`DONE` 상태에서도 기존 blueprint가 있으면 같은 workflow의
  follow-up으로 라우팅된다. 따라서 같은 Nexus session에서 `테스트를 해라` 같은
  후속 명령을 입력하면 직전에 선택한 target workspace를 유지한다.
- Start 화면에서 안전한 target workspace를 미리 선택하면 workflow session에 즉시
  저장되며, resume 이후 `/execute`도 같은 경로를 재사용한다. Trinity control repo
  내부 경로는 실행 전 확인을 다시 요구한다.
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

Central synthesis는 기본적으로 `strong` synthesis 모델을 사용한다. 명시적으로
`synthesis_model = "fast"`를 설정한 경우에만 경량 모델을 사용한다. Model-backed
synthesis가 성공하면 `recommended_blueprint` 안에 실행 후보 `work_packages` graph를
함께 만들 수 있다. 각 work package는 owner, dependency, 예상 파일 범위,
parallel group, `parallelizable`, `risk`를 포함한다.

중앙 synthesis prompt는 WP graph를 실행 가능한 DAG로 만들도록 요구한다. 특히
`expected_files`는 각 package가 쓸 수 있는 가장 좁은 상대 경로를 적고, shared config,
lockfile, schema/type 파일을 건드릴 가능성이 있으면 반드시 포함하도록 안내한다.
`parallel_group`은 실행 wave 후보일 뿐이며, 로컬 policy가 dependency/file/risk 기준으로
다시 직렬화할 수 있다.

`BlueprintDecomposer`는 central work package graph가 있으면 이를 우선 사용한다. 다만
모델 출력을 그대로 실행하지 않고 다음 로컬 보수화를 거친다.

- active agent가 아닌 owner는 현재 세션의 active agent로 재배정한다.
- package id는 `WP-001` 형식으로 재번호화하고 dependency도 최종 id로 정규화한다.
- 자기 자신 dependency와 존재하지 않는 dependency는 제거한다.
- `expected_files`가 비어 있는 실행 package는 unknown write scope로 표시해 병렬 실행을
  무분별하게 허용하지 않는다.
- per-package acceptance criteria가 없으면 blueprint 기준 criteria를 상속한다.
- `parallel_group`이 있으면 같은 group을 먼저 계획하되, dependency/file/risk 정책이
  더 우선한다.
- 보수화 사유는 각 `WorkPackage.repair_notes`에 저장된다. Nexus Central Agent,
  Report, Markdown export에서는 중앙 원본 WP graph, 로컬 WP graph, 로컬 정책 보수 내역을
  분리해서 볼 수 있다.

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
- `src/module/`과 `src/module/file.py`처럼 부모/자식 경로 관계인 파일 소유권도 충돌로 본다.
- `parallelizable=false` 또는 `risk=high` package는 같은 workspace의 다른 writer와
  병렬 실행하지 않는다.
- `pyproject.toml`, `uv.lock`, `package.json`, lockfile, root config 같은 공유 workspace
  파일 변경은 파일 범위가 겹치지 않아도 같은 workspace에서 직렬화한다.
- batch 계획은 `execution_batch_planned` 이벤트로 남으며, 직렬화 사유는 policy notice로
  Execution Matrix log와 report export에서 확인할 수 있다.

공유 파일과 broad root 경로 목록은 `.trinity/trinity.config`의 `[execution]` 섹션에서
조정할 수 있다.

```toml
[execution]
parallel_shared_write_paths = ["pyproject.toml", "uv.lock", "package.json"]
parallel_broad_write_paths = ["src", "tests"]
```

기본값은 보수적이다. `docs`처럼 병렬 작성이 비교적 안전한 영역은 기본 broad root에서
제외되어 있고, 프로젝트 성격상 문서 루트도 직렬화해야 한다면 `parallel_broad_write_paths`에
추가한다.

실행 중에는 각 package의 시작과 종료가 workflow event로 남는다. Textual Execution
Matrix는 이 이벤트를 `[HH:MM:SS] work_package_started: ...`와
`[HH:MM:SS] work_package_completed: ...` 형식으로 표시한다. 같은 정보는
`.trinity/workflow/events.jsonl`의 `timestamp`, `event`, `data.package_id`,
`data.agent`, `data.status`, `data.summary` 필드에서도 확인할 수 있다.

## Textual Workbench의 역할

Textual 앱은 별도 workflow 엔진이 아니다. `TextualWorkflowController`가 기존
`WorkflowEngine`과 `TrinityOrchestrator`를 background thread에서 실행하고,
`TUIEventBus` 이벤트와 persisted workflow state를 snapshot으로 합쳐 화면에 보여준다.

화면 역할은 다음과 같다.

| 화면 | 역할 |
| :--- | :--- |
| Start | 첫 요구사항 작성, 선택적 target workspace 지정 |
| Nexus | provider 상태, central synthesis, 질문, decision, blueprint, package 상태, 실행 결과 요약 표시 |
| Provider Inspector | provider raw output을 탭 modal로 확인 |
| Execute Preflight | target workspace 선택, 경로/git/write 가능성 확인, 필요한 폴더 생성 |
| Execution Matrix | work package table과 execution log 표시 |
| Settings | theme, density, motion, Unicode preference 저장 |

Nexus의 Central Agent 영역은 합의 결과 바로 아래에 WP graph를 표시한다. Central
synthesis가 제안한 graph와 로컬 policy가 보수화한 executable WP graph가 모두 있으면
`Central WP Graph`와 `Local WP Graph`를 분리해서 보여준다. WP 실행 결과가 생기면
package별 상태, executor, summary, 변경 파일, blocker를 `Execution Result Summary`로
요약해 중앙 영역에 남긴다.

Nexus의 Central Agent 영역은 질문과 답변 이력을 모두 유지하는 스크롤 영역이다.
답변 완료 질문은 사용자 답변과 함께 남고, 아직 열린 질문만 선택 버튼을 표시한다.
Central WP graph가 있으면 중앙 원본 graph와 로컬 보수 graph, 보수 사유를 함께 표시한다.
Claude, Codex, Antigravity provider 카드도 스크롤 가능한 패널로 동작해 긴 provider
output을 카드 안에서 계속 확인할 수 있다.

## Plain TUI와 legacy tmux

plain TUI는 `InteractiveSession`이 사용자 입력을 받고 `WorkflowEngine`과
`TrinityOrchestrator`를 직접 호출한다. slash command는 `/status`, `/context`,
`/questions`, `/answer`, `/target`, `/execute`, `/resume` 같은 workflow 조작에 사용된다.
명령별 사용법, 상태 변경, 저장 파일, Textual 팔레트와의 차이는
[Slash Command Reference](slash-command-reference.md)를 기준으로 한다.

Textual Workbench의 `/` 팔레트는 현재 command execution router가 아니라
입력 보조 UI다. `/status` 같은 명령을 Textual composer에서 제출하면 별도 상태 명령이
아니라 Nexus follow-up 텍스트로 들어간다. Textual에서 안정적으로 실행을 시작하는
경로는 Execute 버튼 또는 `Ctrl+E`가 호출하는 `TextualWorkflowController.request_execution()`이다.

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
