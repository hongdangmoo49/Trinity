# Trinity Slash Command Routing Design

작성일: 2026-06-06

대상 버전: Trinity v0.10.3

상태: 설계 기준

## 목표

Trinity 앱 자체 slash command의 동작을 UI 표면과 관계없이 동일하게 정의한다. 사용자가
첫 페이지(Start) 또는 두 번째 페이지(Nexus)에서 `/status`, `/workflow` 같은 명령을
입력했을 때, 해당 명령은 에이전트에게 프롬프트로 전달되지 않아야 한다. 에이전트 호출은
명시적으로 허용된 명령에서만 발생해야 한다.

## 범위

이 문서는 Trinity 앱이 직접 소유하는 top-level slash command만 다룬다.

```text
/status
/context
/rounds
/agent
/history
/save
/caveman
/workflow
/questions
/answer
/decisions
/packages
/subtasks
/report
/resume
/execute
/target
/help
/quit
/exit
/q
```

Claude, Codex, Antigravity CLI 내부 slash command와 `.trinity/agents/*/provider-state`
아래 외부 플러그인 cache command는
[Provider CLI Slash Command Backlog](2026-06-06-provider-cli-slash-command-backlog.md)
에서 별도 과제로 다룬다.

## 라우팅 원칙

1. 입력이 `/`로 시작하면 먼저 Trinity slash command router가 처리한다.
2. command id는 첫 토큰이며, `/`를 제거하고 소문자로 정규화한다.
3. command args는 shell-style quoting을 지원한다. plain TUI의 현재 구현처럼
   `shlex.split()` 호환 동작을 기준으로 한다.
4. 등록되지 않은 slash command는 unknown command로 끝내며, workflow prompt로 넘기지 않는다.
5. 조회/UI 명령은 에이전트를 호출하지 않는다.
6. 설정/세션 변경 명령은 로컬 상태만 바꾸고, 필요한 snapshot/UI만 갱신한다.
7. workflow 명령은 `WorkflowEngine`을 통해 session/event를 저장한다.
8. 에이전트 호출은 `agent_call`이 `deliberation`, `execution`, `conditional`로 명시된
   명령에서만 허용한다.
9. Textual Start와 Nexus는 plain TUI와 같은 registry를 사용해야 한다.
10. Textual slash palette는 command insertion UI가 아니라 command execution entrypoint와
    연결되어야 한다.

## 명령 결과 타입

Textual과 plain TUI가 같은 동작을 공유하려면 command handler는 UI 구현체에 직접 묶이지
않은 결과를 반환해야 한다.

| 결과 타입 | 의미 | 에이전트 호출 |
| :--- | :--- | :--- |
| `render` | 텍스트, 표, 패널, report를 현재 화면에 표시 | 없음 |
| `notify` | 짧은 성공/실패 메시지 표시 | 없음 |
| `snapshot` | workflow/session 변경 후 화면 projection 갱신 | 없음 |
| `open_picker` | workspace picker, resume selector, question selector 같은 로컬 UI 열기 | 없음 |
| `route` | Report, Execution Matrix, Settings 등 앱 내부 화면 전환 | 없음 |
| `deliberate` | `TrinityOrchestrator.ask()` worker 시작 | 있음 |
| `execute` | `TrinityOrchestrator.execute_work_packages()` worker 시작 | 있음 |
| `quit` | 앱 또는 plain TUI loop 종료 | 없음 |
| `error` | 오류 메시지 표시 후 입력 폐기 | 없음 |

## 에이전트 호출 분류

| 분류 | 설명 |
| :--- | :--- |
| `none` | 절대 provider/orchestrator를 호출하지 않는다. |
| `conditional` | 로컬 workflow action을 먼저 수행하고, 그 결과가 재협의를 요구할 때만 호출한다. |
| `execution` | 사용자가 명시적으로 구현 실행을 요청한 경우에만 실행 worker를 호출한다. |

## 표면별 기본 동작

| 표면 | slash command 제출 시 기대 동작 |
| :--- | :--- |
| Plain TUI | 현재처럼 `_handle_command()`가 즉시 실행한다. 출력은 Rich console에 표시한다. |
| Textual Start | 새 workflow를 만들기 전에 command router로 분기한다. `/status`, `/help`, `/resume` 등은 Start 화면에서 처리하고 Nexus로 넘어가지 않는다. |
| Textual Nexus | `submit_follow_up()` 호출 전에 command router로 분기한다. 조회 명령은 central/inspector/report 영역을 갱신하고 에이전트를 호출하지 않는다. |
| Textual palette | 후보 선택은 command text 삽입까지만 하지 않고, 최종 제출 시 router가 command로 실행한다. |

## 명령별 동작 정의

| 명령 | 인자 | 분류 | 에이전트 호출 | 상태/파일 side effect | 기대 동작 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/help` | 없음 | 로컬/UI 조회 | 없음 | 없음 | 사용 가능한 Trinity command 목록과 간단한 사용법을 표시한다. Textual에서는 modal 또는 central log에 표시하고 workflow를 시작하지 않는다. |
| `/status` | 없음 | 로컬/UI 조회 | 없음 | 없음 | agent provider, enabled flag, runtime state, readiness, context, transport mode, synthesis mode, workflow 요약을 표시한다. readiness를 새로 검사하지 않고 현재 projection만 보여준다. |
| `/context` | 없음 | 로컬/UI 조회 | 없음 | 없음 | `config.shared_context_path`의 shared context를 읽어 표시한다. 비어 있으면 empty 안내를 표시한다. 파일을 수정하지 않는다. |
| `/rounds` | `[N]` | 세션 설정 변경 | 없음 | 현재 프로세스 config만 변경 | 인자가 없으면 현재 max deliberation rounds를 표시한다. `1..20` 숫자를 받으면 현재 세션의 `config.max_deliberation_rounds`와 TUI projection을 변경한다. 설정 파일에는 저장하지 않는다. |
| `/agent` | `<name> on\|off` | 세션 설정 변경 | 없음 | 현재 프로세스 config만 변경 | 지정 agent를 현재 세션에서 enable/disable한다. 알 수 없는 agent 또는 잘못된 action은 usage 오류로 끝낸다. 비활성화된 agent는 다음 deliberation/execution부터 제외된다. |
| `/history` | 없음 | 로컬/UI 조회 | 없음 | 없음 | 현재 프로세스의 deliberation history를 표시한다. 기록이 없으면 empty 안내를 표시한다. workflow history archive와는 별개다. |
| `/save` | 없음 | 로컬 파일 기록 | 없음 | `.trinity/history/session_history.json` 기록 | `tui.last_result`가 있으면 history file에 append한다. 결과가 없으면 경고만 표시한다. workflow session 저장 명령으로 오해되지 않게 메시지를 분리한다. |
| `/caveman` | `[on\|off\|lite\|full\|ultra]` | 세션 설정 변경 | 없음 | 현재 프로세스 config만 변경 | 인자가 없으면 현재 caveman compression 상태를 표시한다. `on/off`는 활성 상태를 바꾸고, intensity 값은 모드를 켜면서 강도를 변경한다. 설정 파일에는 저장하지 않는다. |
| `/workflow` | 없음 | 로컬/UI 조회 | 없음 | 없음 | 현재 workflow id, state, goal, round, active agents, target workspace, pending questions, decisions, work packages, parallel groups, subtasks, review packages를 표시한다. |
| `/questions` | `[--select] [--all]` | 로컬/UI 조회 또는 로컬 선택 UI | 없음 | 선택 UI에서 답변하면 workflow 저장 | 인자가 없으면 pending questions를 표시한다. `--select`는 첫 질문 선택 UI를 열고, `--all`은 전체 질문 wizard를 진행한다. 질문 선택 자체는 에이전트를 호출하지 않고, 답변 처리 결과가 재협의를 요구할 때만 `/answer`와 같은 조건부 흐름으로 이어진다. |
| `/answer` | `<id\|index\|next> <answer>`, `<option-index>`, `--replace ...` | 조건부 workflow 변경 | 조건부 | `.trinity/workflow/session.json`, `events.jsonl` | pending question 답변 또는 기존 decision 교체를 기록한다. 아직 남은 질문이 있으면 UI만 갱신한다. 모든 필수 질문이 해결되어 `WorkflowInputAction.should_deliberate`가 true일 때만 deliberation worker를 시작한다. |
| `/decisions` | 없음 | 로컬/UI 조회 | 없음 | 없음 | decision ledger를 표시한다. question id, decision id, decision text, decided_by를 보여준다. |
| `/packages` | 없음 | 로컬/UI 조회 | 없음 | 없음 | 현재 work package 목록, owner, status, execution 여부, dependency, expected files, objective를 표시한다. |
| `/subtasks` | 없음 | 로컬/UI 조회 | 없음 | 없음 | provider 내부 delegation 결과가 있으면 subtask id, parent package, parent agent, delegated target, status, summary를 표시한다. |
| `/report` | `[save\|s]` | 로컬/UI 조회 또는 로컬 파일 기록 | 없음 | `save` 시 `.trinity/reports/*.md` 기록 | 인자가 없으면 현재 workflow/result 기반 report를 표시한다. `save` 또는 `s`는 Markdown report를 저장하고 경로를 표시한다. report data가 없으면 협의를 먼저 시작하라고 안내한다. |
| `/resume` | `[index\|latest\|workflow-id]` | workflow 로컬 변경 | 없음 | active workflow archive/restore | archive 목록을 조회하고 선택된 workflow를 active session으로 복원한다. 현재 active workflow가 있으면 먼저 archive한다. Textual에서는 selector UI 또는 목록 표시 후 snapshot을 갱신한다. 복원만으로 에이전트를 호출하지 않는다. |
| `/target` | `[path\|clear\|reset\|none]` | workflow 로컬 변경 | 없음 | target workspace session/event 저장, path 생성 가능 | 인자가 없으면 현재 target과 기본 후보를 표시한다. `clear/reset/none`은 target을 제거한다. path는 상대 경로를 `config.project_dir` 기준으로 해석하고, 필요하면 폴더를 만든다. control repo 내부 path는 확인 없이는 허용하지 않는다. |
| `/execute` | `[instruction]` | 명시 실행 | execution | blueprint freeze, execution event, package status 변경 | workflow state가 `BLUEPRINT_READY`이고 target workspace가 설정되어 있을 때만 execution worker를 시작한다. target이 없으면 workspace picker를 열거나 `/target` 안내를 표시한다. blueprint가 없으면 에이전트를 호출하지 않고 오류를 표시한다. |
| `/quit` | 없음 | 앱 종료 | 없음 | 없음 | plain TUI loop 또는 Textual app 종료로 처리한다. 진행 중 worker가 있으면 종료 확인 정책을 별도로 둔다. |
| `/exit` | 없음 | 앱 종료 alias | 없음 | 없음 | `/quit`과 동일하다. |
| `/q` | 없음 | 앱 종료 alias | 없음 | 없음 | `/quit`과 동일하다. |

## Textual Start 세부 계약

Start 화면은 아직 사용자의 작업 goal이 확정되지 않은 상태다. 따라서 slash command가 들어오면
새 workflow를 만들지 않는다.

| 명령 분류 | Start 동작 |
| :--- | :--- |
| 로컬/UI 조회 | 현재 가능한 정보만 표시한다. workflow가 없으면 `(none)` 또는 empty 상태를 보여준다. |
| 세션 설정 변경 | 현재 앱 config projection을 바꾸고 Start 화면에 머문다. |
| workflow 로컬 변경 | `/resume`은 archive selector를 열 수 있다. `/target`은 workspace candidate 또는 workflow target을 설정하되 새 goal을 만들지 않는다. |
| 조건부 workflow 변경 | pending question이 없으면 오류를 표시한다. 에이전트를 호출하지 않는다. |
| 명시 실행 | blueprint가 없으므로 "No blueprint is ready" 안내를 표시한다. workspace picker를 열거나 에이전트를 호출하지 않는다. |
| 종료 | 앱 종료 또는 종료 확인을 수행한다. |

## Textual Nexus 세부 계약

Nexus 화면은 active workflow가 있을 수 있다. slash command는 follow-up prompt보다 먼저
해석한다.

| 명령 분류 | Nexus 동작 |
| :--- | :--- |
| 로컬/UI 조회 | central agent history, inspector, report screen, notification 중 적절한 surface를 갱신한다. |
| 세션 설정 변경 | 설정 변경 후 provider strip/snapshot을 갱신한다. |
| workflow 로컬 변경 | `WorkflowEngine`을 갱신하고 `NexusSnapshotAdapter` projection을 다시 적용한다. |
| `/answer` | decision 기록 후 남은 질문이 있으면 질문 UI만 갱신한다. 재협의가 필요할 때만 background deliberation을 시작한다. |
| `/execute` | `TextualWorkflowController.request_execution()`과 같은 실행 경로를 사용한다. target이 없으면 workspace picker를 연다. |
| unknown slash | notification 또는 central log에 오류를 표시하고 composer를 비운다. |

## 공통 registry 설계

향후 구현은 `src/trinity/slash_commands.py` 같은 공통 registry를 두는 방식이 적합하다.

```python
@dataclass(frozen=True)
class SlashCommandSpec:
    name: str
    aliases: tuple[str, ...]
    usage: str
    summary: str
    category: SlashCommandCategory
    agent_call: AgentCallPolicy
    surfaces: frozenset[SlashSurface]
    mutates_workflow: bool = False
    writes_files: bool = False
```

registry는 다음을 생성하는 단일 source of truth가 되어야 한다.

- plain TUI command router
- prompt_toolkit completion list
- Textual palette candidate list
- Textual localized command descriptions
- 문서의 command table
- command coverage tests

## 테스트 기준

| 테스트 | 목적 |
| :--- | :--- |
| registry와 plain handler command set 일치 | 등록된 명령과 실제 실행 가능한 명령 불일치 방지 |
| registry와 Textual palette command set 일치 | 발견성 누락 방지 |
| Start에서 `/status`, `/workflow`, `/questions`, unknown slash 제출 | `start_prompt()`와 `orchestrator.ask()`가 호출되지 않는지 검증 |
| Nexus에서 `/status`, `/workflow`, `/questions`, unknown slash 제출 | `submit_follow_up()`와 `orchestrator.ask()`가 호출되지 않는지 검증 |
| `/answer` pending 질문 일부만 해결 | 에이전트 호출 없이 snapshot만 갱신되는지 검증 |
| `/answer` 마지막 질문 해결 | `should_deliberate=True`일 때만 deliberation worker가 시작되는지 검증 |
| `/execute` blueprint 없음 | 오류 표시, 에이전트 호출 없음 |
| `/execute` target 없음 | workspace picker 또는 target 안내, 에이전트 호출 없음 |
| `/execute` blueprint와 target 있음 | execution worker 호출 |
| unknown slash | workflow prompt로 전달되지 않고 오류 처리 |

## 구현 순서 제안

1. 공통 `SlashCommandSpec` registry를 추가한다.
2. 기존 `TRINITY_COMMANDS`와 Textual `COMMAND_DESCRIPTIONS`를 registry 기반으로 생성한다.
3. plain TUI `_handle_command()`를 registry dispatch로 옮긴다.
4. Textual Start/Nexus 제출 핸들러 앞에 slash command router를 추가한다.
5. 조회 명령의 Textual render target을 정의한다.
6. `/answer`, `/target`, `/resume`, `/execute`의 Textual side effect를
   `TextualWorkflowController` 결과 타입으로 연결한다.
7. 위 테스트 기준을 추가하고 회귀 테스트를 실행한다.

## 결정

Trinity 앱 자체 slash command는 사용자 prompt가 아니다. 따라서 Textual에서 `/`로 시작하는
입력은 기본적으로 에이전트 호출 경로로 넘기지 않는다. 에이전트 호출은 `/answer`의 조건부
재협의와 `/execute`의 명시 실행에만 허용한다.
