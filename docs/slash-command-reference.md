# Slash Command Reference

작성일: 2026-06-06

대상 버전: Trinity v0.12.0

이 문서는 Trinity에서 `/`로 시작하는 인라인 명령어의 현재 구현을 코드 기준으로
정리한다. 기준 구현은 `trinity --plain`이 사용하는 plain TUI의
`InteractiveSession._handle_command()`이며, Textual Workbench는 Start/Nexus 제출 직전에
Trinity slash command를 workflow prompt와 분리해 처리한다.

Trinity 앱 자체 slash command의 목표 라우팅 계약과 명령별 설계는
[Trinity Slash Command Routing Design](plans/2026-06-06-trinity-slash-command-routing-design.md)을
기준으로 하며, Textual Start/Nexus에서 실제로 어떤 UI surface에 표시할지는
[Trinity Slash Command UX Contract](plans/2026-06-07-trinity-slash-command-ux-contract.md)를
따른다. Claude, Codex, Antigravity 같은 provider CLI 내부 slash command와
`.trinity/agents/*/provider-state` 아래 외부 plugin cache command는 Trinity 앱
명령이 아니며,
[Provider CLI Slash Command Backlog](plans/2026-06-06-provider-cli-slash-command-backlog.md)의
후속 과제로 남긴다.

## 실행 표면

| 표면 | 진입 방법 | `/` 처리 방식 |
| :--- | :--- | :--- |
| Textual Workbench | `trinity` | `PromptComposer`가 `/` 후보를 보여주고, Start/Nexus 제출 직전에 Trinity slash command router가 먼저 처리한다. |
| Plain TUI | `trinity --plain` 또는 `TRINITY_TUI=plain` | 입력이 `/`로 시작하면 `InteractiveSession._handle_command()`가 실제 명령으로 실행한다. |
| Prompt completion | plain TUI prompt, Textual composer | `src/trinity/slash_commands.py`의 공통 registry에서 생성한 `TRINITY_COMMANDS` 목록을 사용한다. |
| Execute button | Textual Nexus `Execute`, `Ctrl+E` | slash command가 아니라 `TextualWorkflowController.request_execution()`을 직접 호출한다. |

## Textual 라우팅 보강

현재 Textual Workbench의 첫 페이지(Start)와 두 번째 페이지(Nexus)는 모두 같은
`PromptComposer`를 사용한다. 이 composer는 `/` 입력에 후보를 보여주며, 후보 수락 후
제출된 slash text는 일반 prompt/follow-up으로 넘어가기 전에 앱 레벨 slash command
router로 분기된다.

현재 흐름은 다음과 같다.

| 화면 | 현재 이벤트 흐름 | 결과 |
| :--- | :--- | :--- |
| Start | `PromptComposer.Submitted` -> `StartScreen.SlashCommandSubmitted` -> `TrinityTextualApp._handle_textual_slash_command()` | `/status`, `/workflow`, unknown slash는 새 workflow goal로 들어가지 않고 Start 화면에 머문다. |
| Nexus | `PromptComposer.Submitted` -> `NexusScreen.SlashCommandSubmitted` -> `TrinityTextualApp._handle_textual_slash_command()` | `/workflow`, `/questions`, unknown slash는 Nexus follow-up으로 기록되지 않고 에이전트를 호출하지 않는다. |

Textual slash command 결과는 `LocalCommandSnapshot`으로 정규화된다. Start 화면에서는
긴 결과를 중앙 modal로 보여주고, Nexus에서는 중앙 영역의 `Local Command Results`와
read-only table로 남긴다. `/help`, `/workflow`, `/questions`, `/decisions`,
`/packages`, `/subtasks`, `/history`, `/report`, 설정 명령, unknown slash 모두
일반 prompt/follow-up으로 넘어가지 않는다.

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
팔레트를 연다. 후보는 최대 6개씩 보이며, 위/아래 키로 선택을 이동하고 Enter 또는
Tab으로 선택한 명령 텍스트를 composer에 삽입한다.

중요한 제한은 다음과 같다.

- `/status`, `/workflow`, `/questions` 같은 명령은 Textual에서 workflow prompt/follow-up과
  분리되어 처리된다.
- `/con`처럼 부분 입력 상태의 Enter 또는 Tab은 선택된 후보를 composer에 삽입한다.
  `/context`, `/status`처럼 등록 명령과 정확히 일치하는 입력은 첫 Enter에서 command
  router가 바로 실행되며, Tab은 실행하지 않고 trailing space가 포함된 command text로
  완성한다.
- `/execute`는 slash command와 Nexus의 `Execute` 버튼 또는 `Ctrl+E`가 같은
  `TextualWorkflowController.request_execution()` 계열로 수렴한다.
- `Ctrl+P` 바인딩 문구는 존재하지만, 현재 팔레트는 실제로 `/`를 입력할 때 열린다.

Textual render target은 Markdown 본문과 구조화 table을 함께 쓴다. 동작이 없는 row는
선택 가능한 버튼처럼 보이지 않도록 cursor/selection을 끈 read-only table 또는 plain
text table로 렌더링한다.

`/questions --select`는 Textual에서는 별도 터미널 선택 UI를 열지 않는다. 중앙 질문 영역에
이미 표시되는 option button을 Textual-native 선택 UI로 사용하며, 로컬 명령 결과에는 현재
선택 대상 질문과 `/answer <option-number>` 대체 입력 방법을 남긴다.

## 명령어 요약

| 명령 | 사용법 | 상태 변경 | 동작 요약 |
| :--- | :--- | :--- | :--- |
| `/status` | `/status` | 없음 | agent 상태, readiness, context, transport, synthesis 설정, workflow 요약을 표시한다. |
| `/context` | `/context` | 없음 | 현재 세션의 목표, 합의, 질문, 결정, 작업 패키지 요약을 표시한다. |
| `/project` | `/project [workspace\|analyze]` | 선택 시 로컬 UI | 간결한 프로젝트 진단을 표시하거나 workspace 선택 또는 분석을 연다. |
| `/providers` | `/providers` | 로컬 UI | 프로바이더 인스펙터를 연다. |
| `/workspace` | `/workspace` | 로컬 UI | target workspace 선택 picker를 연다. |
| `/rounds` | `/rounds [N]` | 세션 메모리 | 최대 deliberation round를 조회하거나 1-20 범위 값으로 바꾼다. |
| `/agent` | `/agent [<name> on\|off]` | 세션 메모리 | 현재 세션의 agent 목록을 보거나 agent enable flag와 TUI 표시 상태를 변경한다. |
| `/model` | `/model` | 세션 메모리 | Textual Start/Nexus에서 에이전트별 모델 선택 modal을 열고 다음 요청의 모델 override를 설정한다. |
| `/history` | `/history` | 없음 | 현재 TUI 메모리에 있는 deliberation history를 표시한다. |
| `/save` | `/save` | 파일 기록 | 마지막 deliberation 결과가 있으면 `.trinity/history/session_history.json`에 저장한다. |
| `/caveman` | `/caveman [on\|off\|lite\|full\|ultra]` | 세션 메모리 | 출력 압축 모드와 강도를 조회하거나 바꾼다. |
| `/workflow` | `/workflow` | 없음 | workflow id, state, goal, target workspace, 질문/결정/package 수, 병렬 그룹 수를 표시한다. |
| `/questions` | `/questions [--select] [--all]` | 선택 시 변경 | 열린 workflow 질문을 표시하거나 선택 UI로 답변을 입력한다. |
| `/answer` | `/answer <id\|n\|next> <text>` | workflow 저장 | 질문 답변을 decision으로 기록하고 필요하면 deliberation을 재개한다. |
| `/ask` | `/ask <all\|agent[,agent...]> [--model MODEL] <prompt>` | 조건부 workflow 저장 | 선택한 agent에게만 새 질문이나 follow-up을 보내고, 필요하면 지정 모델 override를 해당 요청에 적용한다. |
| `/decisions` | `/decisions` | 없음 | 기록된 workflow decision ledger를 표시한다. |
| `/packages` | `/packages` | 없음 | 생성된 work package 목록과 실행 여부, dependency, 예상 파일을 표시한다. |
| `/subtasks` | `/subtasks` | 없음 | provider 내부 delegation 결과를 표시한다. |
| `/report` | `/report [save\|s]` | 선택 시 파일 기록 | 협의 결과 개괄 report를 표시하거나 `.trinity/reports/`에 Markdown으로 저장한다. |
| `/resume` | `/resume [n\|latest\|id]` | workflow 저장 | `.trinity/workflow/history/`의 저장 세션을 선택해 active workflow로 복원한다. |
| `/execute` | `/execute [instruction]` | workflow 및 target workspace | 준비된 blueprint를 executable package로 재생성하고 target workspace에서 실행한다. |
| `/execute-retry` | `/execute-retry [all\|failed\|blocked\|interrupted\|custom\|WP-ID...]` | workflow 및 target workspace | 실패, 차단, 중단된 work package를 사용자가 선택해 새 execution run으로 재시도한다. |
| `/review` | `/review [wp\|final\|all] [WP-ID...]` | workflow 저장 | 대기 중인 WP 리뷰 또는 최종 프로젝트 리뷰를 명시적으로 실행한다. |
| `/improve` | `/improve [all\|critical\|high\|AI-ID...\|done\|text]` | 조건부 workflow 및 target workspace | final review 이후 action item을 선택하거나 자유 보강 요청을 supplemental WP로 추가한다. `done`은 로컬 종료만 수행한다. |
| `/target` | `/target [path\|clear]` | workflow 저장, 선택 시 폴더 생성 | 구현 산출물을 쓸 target workspace를 조회, 설정, 초기화한다. |
| `/memory` | `/memory [stats\|compact\|cleanup --oversized-backups [--apply]]` | 로컬 파일 기록 | shared context memory 통계, bounded projection 압축, oversized backup 정리 후보 확인/삭제를 실행한다. |
| `/artifact` | `/artifact <memory-id>` | 없음 | memory index에 기록된 아티팩트 참조와 요약을 표시한다. |
| `/help` | `/help` | 없음 | welcome/help 텍스트를 다시 출력한다. |
| `/quit` | `/quit`, `/exit`, `/q` | 세션 종료 | plain TUI 루프를 종료한다. Textual에서는 종료 확인 modal을 먼저 띄운다. |

## Textual 명령 분류 기준

Textual에서 slash command router를 추가할 때는 각 명령을 다음처럼 분류한다. 기본 원칙은
조회/표시 명령이 절대 에이전트 호출로 넘어가지 않아야 한다는 것이다.

| 분류 | 에이전트 호출 | 명령어 | Textual 기대 동작 |
| :--- | :--- | :--- | :--- |
| 로컬/UI 조회 | 없음 | `/help`, `/status`, `/context`, `/project`, `/providers`, `/workspace`, `/model`, `/history`, `/workflow`, `/questions`, `/decisions`, `/packages`, `/subtasks`, `/report`, `/artifact` | 현재 화면의 central/inspector 영역, notification, modal, 또는 report 화면에 정보를 표시하고 입력은 비운다. `/project` 하위 명령은 에이전트를 호출하지 않고 프로젝트 설정 modal만 연다. |
| 로컬 파일 기록 | 없음 | `/save`, `/report save`, `/memory` | 파일 저장, shared projection 압축, 또는 oversized backup cleanup dry-run/apply 결과를 notification 또는 central log에 표시한다. |
| 세션 설정 변경 | 없음 | `/rounds`, `/agent`, `/caveman` | 현재 프로세스의 설정을 바꾸고 변경 결과를 표시한다. config 파일 저장과는 구분한다. |
| workflow 로컬 변경 | 없음 | `/target`, `/resume` | target workspace 또는 active workflow를 갱신하고 snapshot을 다시 그린다. target 선택이 필요하면 workspace picker를 연다. |
| 조건부 재협의 | 조건부 | `/answer` | 답변을 기록한다. 남은 질문이 있으면 UI만 갱신하고, 모든 질문이 해결되어 `WorkflowInputAction.should_deliberate`가 true일 때만 deliberation worker를 시작한다. |
| 명시 실행 | 있음 | `/execute`, `/execute-retry`, `/review` | blueprint가 준비되어 있고 target workspace가 있으면 execution 또는 review worker를 시작한다. target이 없으면 workspace picker를 열고, blueprint가 없으면 안내만 표시한다. |
| 명시 실행 | 조건부 | `/improve` | `post_review_ready` 상태에서 action item 선택 또는 자유 입력이 supplemental WP를 만들 때만 execution worker를 시작한다. `/improve done`과 목록 조회는 로컬 workflow 갱신만 수행한다. |
| 앱 종료 | 없음 | `/quit`, `/exit`, `/q` | 종료 확인 modal을 표시하고 확인 시에만 Textual 앱을 종료한다. |
| 알 수 없는 명령 | 없음 | 기타 `/...` | 오류와 가까운 후보를 표시하고 `start_prompt()`/`submit_follow_up()`으로 넘기지 않는다. |

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

Textual Start 화면에서는 workflow를 시작하거나 Nexus로 이동하지 않고 status modal을
띄운다. Textual Nexus 화면에서는 중앙 `Local Command Results`의 최신 `/status`
결과를 갱신한다. active workflow가 없는 idle 상태에서는 이전 `shared.md`의
`Agreed Conclusion`을 현재 synthesis로 표시하지 않는다.

Status table의 row는 현재 snapshot에서 만든다. 공통 row는 `Workflow`, `State`,
`Round`, `Goal`이며, 이후 `Provider: <name>` row에는 provider runtime status,
enabled flag, readiness 표시를 합쳐 보여준다. 이 table은 action 목록이 아니라
read-only 요약이다. Textual Start modal에서는 선택 상태가 생기지 않도록 plain
text block으로 표시하고, Nexus의 구조화 table도 row cursor와 선택 동작을 표시하지
않는다.

Readiness가 `not checked`로 보이면 아직 이번 UI 세션에서 provider readiness event를
받지 않았다는 뜻이다. 이 값은 provider가 실패했다는 뜻이 아니라, 현재 status 조회가
새 readiness probe를 실행하지 않았다는 뜻이다.

### `/context`

현재 실행 중인 Trinity session의 요약만 표시한다. 표시 기준은 workflow id, state,
goal, round, synthesis summary/progress, 열린 질문, decision, work package, local
policy repair, 최근 execution log다. 이 명령은 `.trinity/shared.md`나 이전 session
archive를 직접 읽지 않는다.

Textual Start 화면에서는 현재 session 정보가 없으면 workflow를 시작하지 않고
짧은 empty 안내만 표시한다. 현재 session snapshot이 있으면 `/status`와 같은 중앙 modal로
요약을 보여준다. Textual Nexus 화면에서는 중앙 `Local Command Results` 영역에 현재
session context 또는 empty 안내를 남긴다. Plain TUI에서는 같은 기준으로 Rich panel을
출력하고, 현재 session 정보가 없으면 empty 안내만 출력한다.

`resume`으로 이전 Trinity session을 복원한 뒤 어떤 정보를 첫 페이지에서 노출할지는
별도 UX 계약으로 다룬다. `/context` 자체는 복원 여부와 관계없이 현재 active session
projection만 보여준다.

### `/rounds [N]`

인자가 없으면 현재 `config.max_deliberation_rounds`를 출력한다. 숫자 인자가 있으면
1-20 범위를 검증한 뒤 현재 세션의 config object와 TUI 표시 값을 바꾼다.

현재 구현은 설정 파일을 다시 쓰지 않는다. 프로그램을 재시작하면 config 파일에
저장된 값이 다시 적용된다. plain TUI는 명령 출력에, Textual은 Nexus 중앙
`Local Command Results`에 "Session-only setting. Config file was not changed."
안내를 남긴다.

### `/agent <name> on|off`

agent 이름과 `on` 또는 `off`를 받아 현재 세션의 `config.agents[name].enabled` 값을
바꾼다. 활성화하면 TUI agent 상태를 idle로, 비활성화하면 disabled로 표시한다.

이 명령도 현재 프로세스의 config object만 바꾼다. 영구 설정 변경이 필요하면
설정 파일 또는 Settings UI 쪽 기능으로 별도 저장이 필요하다. Textual에서는
인자가 없으면 agent 목록 table을 보여주고, 변경 결과도 중앙 로그에 남긴다.
config 파일 미저장 안내는 항상 함께 표시된다.

### `/history`

Plain TUI에서는 현재 `TrinityTUI.history`에 있는 deliberation history를 표로 출력한다.
prompt, round 수, consensus 여부, duration이 표시된다. 아직 현재 프로세스에서 기록된
history가 없으면 empty message를 출력한다.

Textual에서는 이전 archive를 현재 세션처럼 끌어오지 않는다. 현재 active workflow 요약,
최근 local slash command, 최근 execution log만 `Local Command Results`에 표시한다.
현재 Textual 세션에 표시할 항목이 없으면 empty state를 남긴다. 이전 세션 선택과 복원은
`/resume`의 책임이다.

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

현재 구현은 세션 메모리 값만 변경한다. plain TUI와 Textual 모두 config 파일을
바꾸지 않았다는 안내를 표시하며, Textual에서는 결과가 중앙 로그에 누적된다.

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
모두 등록되어 있다. Textual에서는 report data가 없을 때 toast로만 끝내지 않고
central result 또는 Start modal에 empty state를 남긴다. `/report save`가 성공하면
저장 경로를 central result table과 toast에 모두 남긴다.

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

Textual에서는 인자가 없는 `/resume`이 archive 목록을 `Local Command Results` table에
먼저 남긴 뒤 picker modal을 연다. picker 취소는 취소 결과로 남고, selector 복원 성공 또는
실패도 workflow id/state/goal table과 함께 local result로 남는다. selector 복원에 성공하면
첫 페이지에서 실행했더라도 Nexus로 이동해 해당 workflow 대화를 바로 이어간다.

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
thread에서 실행하고 Execution Matrix에 투영한다. Textual slash `/execute`가 blueprint
준비 전 실행되면 에이전트를 호출하지 않고 `No blueprint is ready` 계열 안내를
local command result로 남긴다.

### `/execute-retry [all|failed|blocked|interrupted|custom|WP-ID...]`

실행 중 종료, provider 실패, 차단 상태로 남은 work package를 새 execution run으로
재시도한다. 기존 `execution_results`, `review_results`, decision log는 삭제하지 않고,
선택된 package만 `pending`으로 되돌린다.

주요 selector는 다음과 같다.

- `all`: retry 가능한 failed, blocked, running package 전체
- `failed`: 실패 package만
- `blocked`: 차단 package만
- `interrupted`: 중단 감지된 running package
- `custom` 또는 `WP-ID...`: 지정 package만

Textual에서는 recovery summary가 있으면 modal/table로 retry 후보를 보여준다. plain TUI는
선택 결과를 출력한 뒤 기존 execution 경로를 재사용한다.

### `/review [wp|final|all] [WP-ID...]`

실행 완료 후 work package 리뷰와 final project review를 명시적으로 실행한다. `wp`는
대기 중인 WP 리뷰만, `final`은 프로젝트 전체 리뷰만, `all`은 WP 리뷰가 모두 승인된 경우
final review까지 이어서 실행한다.

WP review에서 `changes_requested`가 나오면 해당 package의 `repair_notes`에 required
changes를 기록하고, 실제 마지막 executor가 다시 수정하도록 retry execution을 queue한다.
Final review가 승인되거나 변경 요청을 내면 workflow를 바로 `DONE`으로 닫지 않고
`POST_REVIEW_READY`로 전환한다. 이 상태에서 사용자는 `/improve`로 보강 작업을 선택하거나
`/improve done`으로 세션을 닫는다.

### `/improve [all|critical|high|AI-ID...|done|text]`

Final review 이후 `POST_REVIEW_READY` 상태에서만 동작한다. 이 명령은 post-review action
item을 고르거나, 사용자의 자유 보강 요청을 새 action item으로 저장한다.
같은 상태에서 Nexus 일반 채팅으로 보강 요청을 입력해도 동일한 post-review follow-up
경로로 처리된다. `/improve`는 목록 조회, severity/ID 선택, 명시적 종료를 위한
command surface다.

동작은 다음과 같다.

- 인자 없음: 현재 action item 목록과 사용법을 표시한다.
- `done`: 새 실행 없이 workflow를 `DONE`으로 닫는다.
- `all`: 아직 queued/done이 아닌 action item 전체를 보강 대상으로 선택한다.
- `critical`, `high`: 해당 심각도 이상의 action item을 선택한다. `high`는 `critical`도 포함한다.
- `AI-001 AI-004`: 지정 action item만 선택한다.
- 그 밖의 텍스트: 사용자 요청을 `user_request` action item으로 만들고 supplemental WP로 queue한다.

선택된 item은 `accepted` 후 `queued`가 되고, `WP-S001` 같은 supplemental work package가
기존 workflow에 append된다. 이때 기존 WP, execution result, review result는 삭제하지 않는다.
보강 WP는 기존 execution/review/final review 루프를 다시 통과한다.

### `/target [path|clear]`

인자가 없으면 현재 target workspace와 추천 기본 경로를 표시한다. `clear`, `reset`,
`none`은 target workspace를 지우고 `target_workspace_cleared` 이벤트를 기록한다.

경로 인자가 있으면 상대 경로는 `config.project_dir` 기준으로 해석하고, 절대 경로는
그대로 사용한다. plain TUI의 `/target <path>`는 필요한 폴더를 생성할 수 있다.
선택 경로가 Trinity control repo 내부면 사용자 확인을 요구한다. 설정이 완료되면
`target_workspace_selected` 이벤트가 기록되고 workflow session에 경로가 저장된다.

Textual `/target <path>`와 실행 전 workspace preflight도 같은 guardrail을 따른다.
경로가 Textual control repo 내부이면 `TargetWorkspaceConfirmModal`을 먼저 열고,
사용자가 `Use Anyway`를 선택한 경우에만 `control_repo_confirmed=True`로 target을
저장한다. 취소하면 target은 바뀌지 않고 취소 결과가 local result로 남는다.
control repo 바깥 경로는 확인 없이 준비하고, 성공 결과 table에 path, control repo
내부 여부, 확인 여부를 표시한다.

### `/help`

TUI welcome/help 텍스트를 다시 출력한다. 명령 실행 외에 상태를 바꾸지 않는다.
Textual에서는 `src/trinity/slash_commands.py` registry를 기준으로 command, category,
agent call policy, summary를 read-only table로 보여준다.

### `/quit`, `/exit`, `/q`

plain TUI의 `running` flag를 false로 바꿔 메인 루프를 종료한다. 종료 시 goodbye
메시지를 출력한다. Textual에서는 `ConfirmQuitModal`을 먼저 열고, 사용자가 `Quit`을
눌렀을 때만 앱을 종료한다. `Cancel` 또는 `Esc`는 기존 화면으로 돌아간다.

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

1. Plain TUI와 Textual은 같은 registry와 workflow controller를 공유하지만, 표시 surface는
   다르다. Plain TUI는 Rich panel/table, Textual은 Start modal/Nexus central result와
   read-only table을 사용한다.
2. `Ctrl+P`는 command palette binding 문구가 있으나 실제 팔레트는 `/` 입력으로만 열린다.
3. README의 TUI 명령 표는 요약이므로 이 문서를 상세 기준으로 둔다.

이번 문서화 브랜치에서 이미 정리한 발견성 gap은 다음과 같다.

- `/report`를 prompt completion과 Textual slash palette 후보에 추가했다.
- `/exit`, `/q` quit alias를 prompt completion과 Textual slash palette 후보에 추가했다.
- `src/trinity/slash_commands.py` 공통 registry를 추가하고 prompt completion/Textual
  설명이 이 registry를 사용하게 했다.
- plain TUI `_handle_command()`가 `parse_slash_command()`와 registry 기반 dispatch table을
  사용하도록 바꿨다. `/exit`, `/q` 같은 alias는 registry에서 `/quit` canonical command로
  정규화된다.
- Textual Start/Nexus에서 slash command 제출이 `start_prompt()`/`submit_follow_up()`으로
  넘어가지 않도록 `SlashCommandSubmitted` 경로를 추가했다.
- Textual slash command 결과를 `WorkflowNexusSnapshot.local_commands`에 붙이고 Nexus 중앙
  영역의 `Local Command Results` 섹션에 누적 표시한다.
- Textual `/status`, `/workflow` 같은 조회 결과는 Markdown fallback과 함께 중앙 영역의
  `DataTable` 위젯으로도 구조화해 표시한다.
- `/rounds`, `/agent`, `/caveman`은 세션 전용 변경 결과와 config 파일 미저장 안내를
  plain TUI 출력 및 Textual 중앙 로그에 표시한다.
- Textual `/answer`, `/target clear`, `/resume`은 앱이 workflow/persistence private detail을
  직접 만지지 않고 `TextualWorkflowController` public API를 통해 처리한다.
- Textual `/resume` 무인자는 archive 목록 modal을 열고, 선택한 archive를 active workflow로
  복원한 뒤 Nexus로 이동한다. `/resume latest`, `/resume 1`, `/resume <workflow-id>`는 즉시
  복원 경로를 사용한다.
- Textual `/questions --select`는 에이전트를 호출하지 않고 중앙 질문 option button과
  `/answer` 안내를 표시한다.
- Textual 조회 명령은 empty state, action hint, read-only table을 `LocalCommandSnapshot`에
  담아 Start modal과 Nexus central result에서 같은 데이터 기준으로 렌더링한다.
- Textual `/history`는 현재 Textual 세션의 local command/workflow/execution log만 표시하고,
  이전 archive는 `/resume`으로 분리한다.
- Textual `/report`와 `/report save`는 report data 없음/저장 경로를 central result에 남긴다.
- Textual `/agent`, `/rounds`, `/caveman`은 no-arg 조회와 변경 결과 모두 현재 값 table과
  세션 전용 안내를 표시한다.
- Textual `/execute` 준비 실패, `/answer` usage 오류, `/resume` empty/failure, unknown slash도
  toast-only로 끝나지 않고 local command result로 남긴다.
- Textual `/quit`, `/exit`, `/q`는 즉시 종료하지 않고 confirmation modal을 사용한다.
- Textual `/target <path>`는 control repo 내부 target을 확인 모달로 보호하고,
  `/resume` picker 목록/취소/복원 결과를 local command result에 남긴다.
- `tests/test_slash_command_docs.py`가 registry와 이 문서의 명령 요약 표, routing design의
  명령별 policy 표를 비교해 문서 drift를 검출한다.

## 다음 구현 방향

구체적인 목표 동작, command result 타입, Textual Start/Nexus 라우팅 계약, 테스트 기준은
[Trinity Slash Command Routing Design](plans/2026-06-06-trinity-slash-command-routing-design.md)에
정리되어 있다. 현재 남은 구현 방향은 다음과 같다.

1. provider CLI 내부 slash command와 `.trinity/agents/*/provider-state` 아래 외부
   plugin cache command는 [Provider CLI Slash Command Backlog](plans/2026-06-06-provider-cli-slash-command-backlog.md)에서
   별도 정의한다.
