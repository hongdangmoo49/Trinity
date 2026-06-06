# Slash Command Reference

작성일: 2026-06-06

대상 버전: Trinity v0.10.3

이 문서는 Trinity에서 `/`로 시작하는 인라인 명령어의 현재 구현을 코드 기준으로
정리한다. 기준 구현은 `trinity --plain`이 사용하는 plain TUI의
`InteractiveSession._handle_command()`이다. 기본 Textual Workbench의 `/` 팔레트는
현재 명령 실행기가 아니라 입력 보조 UI이므로 별도 섹션으로 구분한다.

## 실행 표면

| 표면 | 진입 방법 | `/` 처리 방식 |
| :--- | :--- | :--- |
| Textual Workbench | `trinity` | `PromptComposer`가 `/`로 시작하는 입력에 후보를 보여준다. 제출된 텍스트는 Nexus follow-up으로 전달된다. |
| Plain TUI | `trinity --plain` 또는 `TRINITY_TUI=plain` | 입력이 `/`로 시작하면 `InteractiveSession._handle_command()`가 실제 명령으로 실행한다. |
| Prompt completion | plain TUI prompt, Textual composer | `src/trinity/tui/prompt.py`의 `TRINITY_COMMANDS` 목록을 사용한다. |
| Execute button | Textual Nexus `Execute`, `Ctrl+E` | slash command가 아니라 `TextualWorkflowController.request_execution()`을 직접 호출한다. |

## 현재 관찰된 Textual 라우팅 문제

현재 Textual Workbench의 첫 페이지(Start)와 두 번째 페이지(Nexus)는 모두 같은
`PromptComposer`를 사용한다. 이 composer는 `/` 입력에 후보를 보여주지만, 제출 시점에
slash command를 실행 라우터로 분기하지 않는다.

현재 흐름은 다음과 같다.

| 화면 | 현재 이벤트 흐름 | 결과 |
| :--- | :--- | :--- |
| Start | `PromptComposer.Submitted` -> `StartScreen.Submitted` -> `TrinityTextualApp.on_start_screen_submitted()` -> `TextualWorkflowController.start_prompt()` | `/status` 같은 문자열도 새 workflow goal로 들어가고, 곧바로 deliberation worker가 시작되어 에이전트를 호출할 수 있다. |
| Nexus | `PromptComposer.Submitted` -> `NexusScreen.FollowUpSubmitted` -> `TrinityTextualApp.on_nexus_screen_follow_up_submitted()` -> `TextualWorkflowController.submit_follow_up()` | `/workflow`, `/questions` 같은 문자열도 workflow follow-up으로 처리되어 상태에 따라 deliberation 또는 execution으로 이어질 수 있다. |

즉, Textual에서 `/` 팔레트가 보여주는 항목은 현재 "명령 실행"이 아니라 "명령 텍스트
삽입"에 가깝다. 사용자는 `/status`를 입력하면 status UI를 기대하지만, 실제로는
에이전트에게 `/status`라는 사용자 요청을 보내는 경로로 들어갈 수 있다.

수정 방향은 제출 직전에 slash command를 먼저 검사하는 것이다. Textual의 Start/Nexus
제출 핸들러는 `start_prompt()` 또는 `submit_follow_up()`을 호출하기 전에 다음 정책을
적용해야 한다.

1. 입력이 `/`로 시작하면 slash command router로 보낸다.
2. 로컬/UI 명령은 화면 갱신, notification, modal, inspector, report 화면 전환 등으로
   끝내고 에이전트를 호출하지 않는다.
3. workflow 상태만 바꾸는 명령은 `WorkflowEngine`/설정 객체를 직접 갱신하고 끝낸다.
4. 에이전트 호출이 필요한 명령은 `/execute` 또는 답변 완료 후 재협의가 필요한
   `/answer`처럼 명시적으로 분류된 경우에만 worker를 시작한다.
5. 알 수 없는 slash command는 "Unknown command"를 보여주고 workflow prompt로 넘기지
   않는다.

## Plain TUI 명령 라우팅

Plain TUI의 메인 루프는 입력을 받은 뒤 `user_input.startswith("/")`이면
명령 모드로 보낸다. 명령 문자열은 선행 `/`를 제거한 뒤 `shlex.split()`으로
분리한다. 따라서 따옴표를 사용해 공백이 포함된 인자를 하나로 묶을 수 있고,
따옴표가 깨지면 명령은 실행되지 않고 syntax error가 출력된다.

라우팅 규칙은 다음과 같다.

1. 첫 토큰을 소문자 command id로 사용한다.
2. 나머지 토큰을 command args로 넘긴다.
3. 지원하지 않는 command id는 `Unknown command`로 끝난다.
4. Workflow 관련 명령은 `WorkflowEngine`을 변경하고 `.trinity/workflow/session.json`
   및 `.trinity/workflow/events.jsonl`에 저장된다.
5. 조회 명령은 대부분 화면 출력만 수행하고 workflow 상태를 변경하지 않는다.

## Textual Workbench의 현재 `/` 팔레트

Textual의 `PromptComposer`는 입력 전체가 `/`로 시작하고 아직 공백이 없을 때만
팔레트를 연다. 후보는 최대 6개씩 보이며, 위/아래 키로 선택을 이동하고 Enter로
선택한 명령 텍스트를 composer에 삽입한다.

중요한 제한은 다음과 같다.

- `/status`, `/workflow`, `/questions` 같은 명령은 Textual에서 별도 명령으로 실행되지 않는다.
- Textual에서 Enter로 제출하면 `NexusScreen.FollowUpSubmitted`가 발생하고,
  `TextualWorkflowController.submit_follow_up()`을 통해 workflow 입력으로 처리된다.
- `/execute`는 텍스트에 포함된 명시 실행 marker로 해석될 수 있지만, 안정적인 실행
  경로는 Nexus의 `Execute` 버튼 또는 `Ctrl+E`다.
- `Ctrl+P` 바인딩 문구는 존재하지만, 현재 팔레트는 실제로 `/`를 입력할 때 열린다.

따라서 다음 편의 기능을 구현할 때는 Textual에도 plain TUI와 같은 명령 라우터를
추가하거나, 공통 command registry를 만들어 두 UI가 같은 동작을 공유하게 하는 것이
가장 안전하다.

## 명령어 요약

| 명령 | 사용법 | 상태 변경 | 동작 요약 |
| :--- | :--- | :--- | :--- |
| `/status` | `/status` | 없음 | agent 상태, readiness, context, transport, synthesis 설정, workflow 요약을 표시한다. |
| `/context` | `/context` | 없음 | shared context 파일 내용을 패널로 표시한다. |
| `/rounds` | `/rounds [N]` | 세션 메모리 | 최대 deliberation round를 조회하거나 1-20 범위 값으로 바꾼다. |
| `/agent` | `/agent <name> on\|off` | 세션 메모리 | 현재 세션의 agent enable flag와 TUI 표시 상태를 변경한다. |
| `/history` | `/history` | 없음 | 현재 TUI 메모리에 있는 deliberation history를 표시한다. |
| `/save` | `/save` | 파일 기록 | 마지막 deliberation 결과가 있으면 `.trinity/history/session_history.json`에 저장한다. |
| `/caveman` | `/caveman [on\|off\|lite\|full\|ultra]` | 세션 메모리 | 출력 압축 모드와 강도를 조회하거나 바꾼다. |
| `/workflow` | `/workflow` | 없음 | workflow id, state, goal, target workspace, 질문/결정/package 수, 병렬 그룹 수를 표시한다. |
| `/questions` | `/questions [--select] [--all]` | 선택 시 변경 | 열린 workflow 질문을 표시하거나 선택 UI로 답변을 입력한다. |
| `/answer` | `/answer <id\|n\|next> <text>` | workflow 저장 | 질문 답변을 decision으로 기록하고 필요하면 deliberation을 재개한다. |
| `/decisions` | `/decisions` | 없음 | 기록된 workflow decision ledger를 표시한다. |
| `/packages` | `/packages` | 없음 | 생성된 work package 목록과 실행 여부, dependency, 예상 파일을 표시한다. |
| `/subtasks` | `/subtasks` | 없음 | provider 내부 delegation 결과를 표시한다. |
| `/report` | `/report [save\|s]` | 선택 시 파일 기록 | 협의 결과 개괄 report를 표시하거나 `.trinity/reports/`에 Markdown으로 저장한다. |
| `/resume` | `/resume [n\|latest\|id]` | workflow 저장 | `.trinity/workflow/history/`의 저장 세션을 선택해 active workflow로 복원한다. |
| `/execute` | `/execute [instruction]` | workflow 및 target workspace | 준비된 blueprint를 executable package로 재생성하고 target workspace에서 실행한다. |
| `/target` | `/target [path\|clear]` | workflow 저장, 선택 시 폴더 생성 | 구현 산출물을 쓸 target workspace를 조회, 설정, 초기화한다. |
| `/help` | `/help` | 없음 | welcome/help 텍스트를 다시 출력한다. |
| `/quit` | `/quit`, `/exit`, `/q` | 세션 종료 | plain TUI 루프를 종료한다. |

## Textual 명령 분류 기준

Textual에서 slash command router를 추가할 때는 각 명령을 다음처럼 분류한다. 기본 원칙은
조회/표시 명령이 절대 에이전트 호출로 넘어가지 않아야 한다는 것이다.

| 분류 | 에이전트 호출 | 명령어 | Textual 기대 동작 |
| :--- | :--- | :--- | :--- |
| 로컬/UI 조회 | 없음 | `/help`, `/status`, `/context`, `/history`, `/workflow`, `/questions`, `/decisions`, `/packages`, `/subtasks`, `/report` | 현재 화면의 central/inspector 영역, notification, modal, 또는 report 화면에 정보를 표시하고 입력은 비운다. |
| 로컬 파일 기록 | 없음 | `/save`, `/report save` | 파일 저장 후 저장 경로를 notification 또는 central log에 표시한다. |
| 세션 설정 변경 | 없음 | `/rounds`, `/agent`, `/caveman` | 현재 프로세스의 설정을 바꾸고 변경 결과를 표시한다. config 파일 저장과는 구분한다. |
| workflow 로컬 변경 | 없음 | `/target`, `/resume` | target workspace 또는 active workflow를 갱신하고 snapshot을 다시 그린다. target 선택이 필요하면 workspace picker를 연다. |
| 조건부 재협의 | 조건부 | `/answer` | 답변을 기록한다. 남은 질문이 있으면 UI만 갱신하고, 모든 질문이 해결되어 `WorkflowInputAction.should_deliberate`가 true일 때만 deliberation worker를 시작한다. |
| 명시 실행 | 있음 | `/execute` | blueprint가 준비되어 있고 target workspace가 있으면 execution worker를 시작한다. target이 없으면 workspace picker를 열고, blueprint가 없으면 안내만 표시한다. |
| 앱 종료 | 없음 | `/quit`, `/exit`, `/q` | Textual 앱 종료 또는 현재 세션 종료 확인으로 처리한다. |
| 알 수 없는 명령 | 없음 | 기타 `/...` | 오류를 표시하고 `start_prompt()`/`submit_follow_up()`으로 넘기지 않는다. |

첫 페이지(Start)에서 slash command가 들어온 경우도 같은 정책을 적용한다. 예를 들어
`/status`, `/help`, `/resume`은 새 workflow를 만들지 않고 로컬 UI로 처리해야 한다.
`/execute`는 아직 blueprint가 없으므로 "No blueprint is ready" 안내로 끝나야 한다.

## 명령별 동작

### `/status`

현재 agent별 provider, enable 상태, runtime state, readiness, context bar를 표로
출력한다. 이어서 transport mode와 synthesis 설정을 표시하고, 내부적으로
`/workflow`와 같은 workflow 요약도 함께 출력한다.

이 명령은 조회 전용이다. provider readiness를 새로 검사하지 않고 현재 TUI 상태와
config/session projection을 보여준다.

### `/context`

`config.shared_context_path`를 `SharedContextEngine`으로 읽어 shared context 내용을
그대로 표시한다. 내용이 비어 있으면 empty message를 출력한다.

### `/rounds [N]`

인자가 없으면 현재 `config.max_deliberation_rounds`를 출력한다. 숫자 인자가 있으면
1-20 범위를 검증한 뒤 현재 세션의 config object와 TUI 표시 값을 바꾼다.

현재 구현은 설정 파일을 다시 쓰지 않는다. 프로그램을 재시작하면 config 파일에
저장된 값이 다시 적용된다.

### `/agent <name> on|off`

agent 이름과 `on` 또는 `off`를 받아 현재 세션의 `config.agents[name].enabled` 값을
바꾼다. 활성화하면 TUI agent 상태를 idle로, 비활성화하면 disabled로 표시한다.

이 명령도 현재 프로세스의 config object만 바꾼다. 영구 설정 변경이 필요하면
설정 파일 또는 Settings UI 쪽 기능으로 별도 저장이 필요하다.

### `/history`

현재 `TrinityTUI.history`에 있는 deliberation history를 표로 출력한다. prompt,
round 수, consensus 여부, duration이 표시된다. 아직 현재 프로세스에서 기록된
history가 없으면 empty message를 출력한다.

### `/save`

마지막 deliberation 결과가 있어야 동작한다. 결과가 없으면 경고만 출력한다.
저장 대상은 `.trinity/history/session_history.json`이며, 기존 JSON을 읽어 현재
TUI history를 append한 뒤 다시 쓴다. 깨진 JSON이면 빈 배열로 복구해 저장한다.

이 명령은 workflow session 저장과 다르다. workflow session은 `WorkflowEngine`이
상태 변화 시 자동으로 `.trinity/workflow/session.json`에 저장한다.

### `/caveman [on|off|lite|full|ultra]`

인자가 없으면 현재 caveman compression mode와 intensity를 출력한다. `on` 또는
`enable`은 현재 intensity로 모드를 켜고, `off` 또는 `disable`은 끈다.
`lite`, `full`, `ultra`는 모드를 켜면서 강도를 해당 값으로 설정한다.

현재 구현은 세션 메모리 값만 변경한다.

### `/workflow`

현재 workflow session의 핵심 상태를 패널로 표시한다.

표시 항목은 workflow id, state, goal, round, active agents, target workspace,
pending questions, decisions, work packages, parallel groups, subtasks,
review packages다. blueprint가 준비된 상태라면 다음 행동으로 `/target`,
`/execute`, 구현 요청, 설계 다듬기, `/workflow`를 안내한다.

### `/questions [--select] [--all]`

기본 동작은 열린 workflow 질문을 패널로 표시하는 것이다. 질문에는 id, 질문 내용,
추천 옵션, 선택지, 답변 방법이 포함된다.

`--select` 또는 `-s`를 붙이면 터미널 선택 UI를 열어 첫 번째 pending question에
답한다. `--all`, `--wizard`, `-a`를 함께 붙이면 열린 질문을 순서대로 계속 묻는다.
비대화형 환경에서는 선택 UI를 열 수 없으므로 `/answer <id|n|next> <answer>` 사용을
안내한다.

### `/answer`

지원 형식은 다음과 같다.

```text
/answer <question-id|index|next> <answer>
/answer <option-index>
/answer --replace <question-id|decision-id> <answer>
```

일반 답변은 `WorkflowEngine.answer_question()`으로 전달된다. 질문은 id, 1부터
시작하는 index, `next` 또는 `first`로 찾는다. 질문이 option을 갖고 있고
`/answer 1`처럼 숫자 하나만 입력하면 첫 번째 open question의 option index로
해석한다.

답변이 기록되면 질문 상태가 answered가 되고 `DecisionRecord`가 추가된다.
`--replace`는 이미 답변한 질문 또는 해당 decision id를 찾아 기존 decision을
갱신한다. 답변 후 `WorkflowInputAction.should_deliberate`가 true면 같은 workflow
문맥으로 deliberation이 다시 시작된다.

### `/decisions`

현재 workflow session의 decision ledger를 표로 출력한다. decision id, 연결된
question id, decision text, 결정 주체가 표시된다.

### `/packages`

현재 workflow session의 work package를 표로 표시한다. package id, owner,
status, 실행 대상 여부, dependency, 예상 파일, estimated weight, objective가
포함된다. 실행 대상이 아닌 planning-only package는 status가 `planning_only`로
표시된다.

### `/subtasks`

execution 중 provider가 내부 delegation을 기록한 경우 subtask id, parent package,
parent agent, delegated target, status, summary를 표시한다.

### `/report [save|s]`

`DeliberationReportBuilder`가 현재 `WorkflowSession`과 마지막
`DeliberationResult`를 바탕으로 개괄 report를 만든다. 세션 goal도 없고 마지막
결과도 없으면 먼저 협의를 시작하라고 안내한다.

인자가 없으면 Rich renderable report를 화면에 출력한다. `save` 또는 `s`를 붙이면
`.trinity/reports/report-<session-prefix>-<timestamp>.md` 형식으로 Markdown 파일을
쓴다.

`/report`는 plain TUI 실행 핸들러와 prompt completion/Textual slash palette 후보에
모두 등록되어 있다.

### `/resume [n|latest|id]`

`.trinity/workflow/history/`의 archive 목록을 읽는다. archive가 없으면 종료한다.
인자가 없고 대화형 터미널이면 선택 UI를 띄운다. 비대화형이면 archive 표와 usage를
출력한다.

선택자는 다음을 지원한다.

- `latest`, `last`, `newest`: 가장 최신 archive
- 숫자: 화면에 표시된 1-based index
- workflow id: 정확히 일치하는 archive id

복원 전 현재 active workflow가 있으면 archive로 저장한 뒤 선택한 archive를 active
session으로 복원한다. 이후 `WorkflowEngine`을 다시 만들고 `/workflow` 요약을
출력한다.

### `/execute [instruction]`

현재 workflow state가 `BLUEPRINT_READY`여야 한다. blueprint가 없거나 아직 준비되지
않았으면 실행하지 않는다. target workspace가 없으면 먼저 target workspace 선택을
요구한다.

실행 흐름은 다음과 같다.

1. target workspace가 존재하고 쓸 수 있는지 확인한다.
2. Trinity control repo 내부를 target으로 쓰려 하면 명시 확인을 요구한다.
3. `WorkflowEngine.enable_execution_for_current_blueprint()`가 현재 blueprint를
   `.trinity/workflow/blueprints/<workflow-id>.json`에 freeze한다.
4. blueprint를 executable work package로 다시 분해한다.
5. 선택 instruction이 있으면 user decision으로 기록한다.
6. `implementation_requested`, `work_package_started`, `work_package_completed`,
   `execution_result_recorded` 이벤트가 workflow event log에 기록된다.
7. execution protocol이 dependency와 file ownership을 고려해 병렬 실행한다.
8. 모든 executable package가 done이면 review package를 만들고 state를 `reviewing`으로
   전환한다. failed 또는 blocked가 있으면 각각 `failed` 또는 `needs_user_decision`으로
   전환한다.

Plain TUI에서는 execution 중 Rich Live 화면을 갱신한다. Textual에서는 Execute 버튼
또는 `Ctrl+E`가 같은 `WorkflowEngine`/`TrinityOrchestrator` 계층을 background
thread에서 실행하고 Execution Matrix에 투영한다.

### `/target [path|clear]`

인자가 없으면 현재 target workspace와 추천 기본 경로를 표시한다. `clear`, `reset`,
`none`은 target workspace를 지우고 `target_workspace_cleared` 이벤트를 기록한다.

경로 인자가 있으면 상대 경로는 `config.project_dir` 기준으로 해석하고, 절대 경로는
그대로 사용한다. plain TUI의 `/target <path>`는 필요한 폴더를 생성할 수 있다.
선택 경로가 Trinity control repo 내부면 사용자 확인을 요구한다. 설정이 완료되면
`target_workspace_selected` 이벤트가 기록되고 workflow session에 경로가 저장된다.

### `/help`

TUI welcome/help 텍스트를 다시 출력한다. 명령 실행 외에 상태를 바꾸지 않는다.

### `/quit`, `/exit`, `/q`

plain TUI의 `running` flag를 false로 바꿔 메인 루프를 종료한다. 종료 시 goodbye
메시지를 출력한다.

## 일반 텍스트 입력과 실행 의도

`/`로 시작하지 않는 입력은 plain TUI와 Textual 모두 workflow state machine으로
전달된다. 기존 blueprint가 없으면 새 workflow goal로 시작한다. `NEEDS_USER_DECISION`
상태에서는 일반 텍스트가 다음 open question 답변으로 처리된다.

기존 blueprint가 있는 상태에서는 입력 내용이 follow-up으로 분류된다. `구현해`,
`이대로 만들어`, `/execute` 같은 명시 실행 marker는 실행 요청으로 분류될 수 있고,
설계/계획 marker는 blueprint 보강 deliberation으로 이어진다.

## 저장 파일과 이벤트

| 경로 | 관련 명령 | 내용 |
| :--- | :--- | :--- |
| `.trinity/workflow/session.json` | `/answer`, `/target`, `/execute`, `/resume` 등 | 현재 workflow state, 질문, 결정, blueprint, package, 실행 결과 |
| `.trinity/workflow/events.jsonl` | workflow 변경 명령 | state transition, target selection, execution package timeline |
| `.trinity/workflow/history/` | `/resume`, startup archive | 이전 active workflow archive |
| `.trinity/workflow/blueprints/` | `/execute` | 실행 시점에 고정한 blueprint artifact |
| `.trinity/history/session_history.json` | `/save` | plain TUI deliberation history |
| `.trinity/reports/` | `/report save` | Markdown report export |

## 현재 불일치와 개선 후보

1. Textual Workbench의 `/` 팔레트는 명령 실행기가 아니다. `/status`를 제출하면 status
   화면이 아니라 workflow start/follow-up으로 들어가 에이전트를 호출할 수 있다.
2. `Ctrl+P`는 command palette binding 문구가 있으나 실제 팔레트는 `/` 입력으로만 열린다.
3. `/rounds`, `/agent`, `/caveman`은 현재 세션 메모리만 바꾸며 config 파일에 저장하지 않는다.
4. README의 TUI 명령 표는 요약이므로 이 문서를 상세 기준으로 둔다.

이번 문서화 브랜치에서 이미 정리한 발견성 gap은 다음과 같다.

- `/report`를 prompt completion과 Textual slash palette 후보에 추가했다.
- `/exit`, `/q` quit alias를 prompt completion과 Textual slash palette 후보에 추가했다.

## 다음 구현 방향

편의 기능을 추가한다면 우선 공통 slash command registry를 만드는 것이 좋다.

권장 구조는 다음과 같다.

1. command id, aliases, args schema, description, mutability, supported surfaces를
   하나의 registry에 정의한다.
2. plain TUI의 `_handle_command()`와 Textual의 `PromptComposer`가 같은 registry를
   사용한다.
3. Textual에는 제출 전 slash command를 감지하는 라우터를 추가하고, 조회 명령은
   notification/modal/inspector update로, workflow 변경 명령은
   `TextualWorkflowController` outcome으로 처리한다.
4. Textual Start/Nexus 제출 테스트는 `/status`, `/workflow`, `/questions`, unknown slash가
   `start_prompt()`/`submit_follow_up()` 또는 `orchestrator.ask()`로 넘어가지 않는지
   확인해야 한다.
5. alias와 discoverability gap을 registry 테스트로 막는다.
6. 세션 메모리 변경 명령과 config persistence 명령을 분리해 사용자에게 저장 여부를
   명확히 보여준다.
