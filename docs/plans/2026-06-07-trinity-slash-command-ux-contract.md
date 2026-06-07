# Trinity Slash Command UX Contract

작성일: 2026-06-07

대상 버전: Trinity v0.10.3+

상태: 구현 전 UX 계약 초안

## 목적

Trinity 앱 자체 slash command를 증상별로 고치는 방식을 중단하고, Start/Nexus/plain TUI에서
각 명령이 어떤 UI surface에 어떤 상태로 표시되어야 하는지 한 번에 정의한다.

이 문서는 다음을 고정한다.

1. slash command 입력과 자동완성의 기본 동작
2. Start 화면과 Nexus 화면의 표시 원칙
3. 명령별 UI surface, empty state, side effect, 에이전트 호출 여부
4. 한 번에 구현할 작업 순서와 회귀 테스트 기준

## 범위

이 문서는 Trinity 앱이 직접 소유하는 top-level slash command만 다룬다.

```text
/help
/status
/context
/workflow
/questions
/answer
/decisions
/packages
/subtasks
/history
/report
/report save
/save
/rounds
/agent
/caveman
/target
/resume
/execute
/quit
/exit
/q
unknown /...
```

Provider CLI 내부 slash command와 `.trinity/agents/*/provider-state` 아래 외부 plugin
cache command는 이 UX 계약의 범위가 아니다.

## 공통 원칙

| 원칙 | 계약 |
| :--- | :--- |
| Slash 우선 라우팅 | 입력이 `/`로 시작하면 Start/Nexus prompt 또는 follow-up으로 넘기기 전에 Trinity slash command router가 먼저 처리한다. |
| 에이전트 호출 금지 | 조회, 설정, 도움말, 저장 안내, unknown command는 provider/orchestrator를 호출하지 않는다. |
| 명시 실행만 실행 | `/execute`만 execution worker를 시작할 수 있다. `/answer`는 workflow action 결과가 재협의를 요구할 때만 조건부로 worker를 시작한다. |
| Start는 새 goal 생성 금지 | Start에서 slash command를 실행해도 새 workflow를 만들거나 자동으로 Nexus로 이동하지 않는다. 단, `/resume` 선택 완료처럼 active workflow를 복원한 경우는 Nexus로 이동할 수 있다. |
| Nexus는 기록 보존 | Nexus에서 실행한 local slash command 결과는 중앙 `Local Command Results`에 남고 스크롤로 다시 볼 수 있어야 한다. |
| Toast는 보조 알림 | 긴 내용은 toast로만 보여주지 않는다. toast는 성공/실패 한 줄 알림과 modal/central 갱신의 보조 신호로 제한한다. |
| Empty state 명시 | 데이터가 없으면 조용히 실패하지 않고 command별 empty state를 표시한다. |
| Read-only UI는 클릭처럼 보이지 않게 | 동작 없는 table row, title, label은 cursor/selection/버튼 스타일을 쓰지 않는다. |
| 설정 변경은 세션 전용 | `/rounds`, `/agent`, `/caveman`은 현재 프로세스 config projection만 바꾸며 config 파일 저장과 구분한다. |
| 파일 기록은 경로 표시 | `/report save`처럼 파일을 쓰는 명령은 저장 경로를 central result와 toast에 모두 남긴다. |

## 입력 UX

| 입력 상태 | Enter | Tab |
| :--- | :--- | :--- |
| `/` 또는 `/con` 같은 부분 입력 | 선택된 후보를 composer에 삽입한다. | 선택된 후보를 composer에 삽입한다. |
| `/context`, `/status` 같은 exact command | command router를 즉시 실행한다. | 실행하지 않고 trailing space가 포함된 command text로 완성한다. |
| `/rounds 7`처럼 인자가 있는 command | command router를 즉시 실행한다. | 일반 입력으로 둔다. |
| unknown `/foo` | unknown command 결과를 표시하고 prompt/follow-up으로 넘기지 않는다. | 후보가 없으면 입력을 유지한다. |

자동완성은 `src/trinity/slash_commands.py` registry를 단일 source of truth로 사용한다.

## Surface 정의

| Surface | 용도 | 사용 위치 |
| :--- | :--- | :--- |
| Start modal | Start에서 긴 조회 결과 또는 설정 UI를 보여준다. | `/help`, `/status`, `/context`, `/workflow`, `/decisions`, `/packages`, `/subtasks`, `/history`, `/rounds`, `/agent`, `/caveman` |
| Start toast | Start에서 정보가 없거나 짧은 결과만 필요한 경우 보조 알림으로 쓴다. | empty state, 저장/오류 안내 |
| Nexus central result | Nexus에서 local slash command의 본문, table, 저장 경로, empty state를 남긴다. | 대부분의 local command |
| Nexus focused region | 기존 질문/패키지/report 영역이 있을 때 해당 영역을 갱신하거나 focus한다. | `/questions`, `/packages`, `/report` |
| Picker modal | 선택지가 있는 workflow-local 명령을 처리한다. | `/resume`, `/target`, `/questions --select` |
| Confirmation modal | 실행/종료처럼 영향이 큰 명령을 확인한다. | `/execute`, `/quit`, `/exit`, `/q` |
| Report screen | report data가 충분할 때 전체 보고서를 표시한다. | `/report` |
| Workspace picker | target workspace가 필요한 실행 흐름에서 사용한다. | `/target`, `/execute` |

## 명령별 UX 계약

| 명령 | Start UX | Nexus UX | Empty/Error UX | 에이전트 호출 |
| :--- | :--- | :--- | :--- | :--- |
| `/help` | 중앙 modal에 명령 목록, 카테고리, 주요 키를 표시한다. | central result에 같은 내용을 남긴다. | 없음 | 없음 |
| `/status` | 중앙 modal에 workflow/provider/readiness 요약을 표시한다. | central result와 read-only table을 갱신한다. | provider readiness가 없으면 `not checked`로 표시한다. | 없음 |
| `/context` | 현재 session 정보가 있으면 중앙 modal, 없으면 짧은 empty toast를 표시한다. | central result에 현재 session 요약 또는 empty message를 남긴다. | 이전 `shared.md`/archive 내용을 현재 session처럼 보여주지 않는다. | 없음 |
| `/workflow` | 중앙 modal에 workflow 요약을 표시한다. | central result에 workflow 요약 table을 남긴다. | active workflow가 없으면 `(new)`, `idle`, `(none)` 중심 empty summary를 표시한다. | 없음 |
| `/questions` | 중앙 modal 또는 toast로 pending question이 없음을 표시한다. | 중앙 질문 영역을 갱신하고 local result에 질문 목록을 남긴다. | 질문이 없으면 명확한 empty message를 남긴다. | 없음 |
| `/questions --select` | 질문이 없으면 empty 안내를 표시한다. | 첫 pending question의 option 선택 UI를 focus하거나 picker를 연다. | option이 없으면 `/answer <id> <text>` 안내를 표시한다. | 없음 |
| `/answer` | pending question이 없으면 오류를 표시한다. | 답변을 기록하고 snapshot을 갱신한다. 필요할 때만 재협의를 시작한다. | id/index가 틀리면 usage와 후보를 표시한다. | 조건부 |
| `/decisions` | 중앙 modal에 decision ledger를 표시한다. | central result에 decision ledger를 남긴다. | decision이 없으면 empty message를 표시한다. | 없음 |
| `/packages` | 중앙 modal에 work package 목록/table을 표시한다. | central result에 package table을 남긴다. | package가 없으면 blueprint가 아직 없다는 안내를 표시한다. | 없음 |
| `/subtasks` | 중앙 modal에 subtask 목록/table을 표시한다. | central result에 subtask table을 남긴다. | subtask가 없으면 provider delegation 기록이 없다는 안내를 표시한다. | 없음 |
| `/history` | 중앙 modal에 현재 프로세스/session history를 표시한다. | central result에 history summary를 남긴다. | history가 없으면 empty message를 표시한다. | 없음 |
| `/report` | report data가 있으면 report modal 또는 Report 화면으로 이동한다. | Report 화면으로 이동하고 central result에 요약을 남긴다. | report data가 없으면 협의를 먼저 시작하라고 안내한다. | 없음 |
| `/report save` | 저장할 report data가 있으면 파일 저장 후 경로를 표시한다. | central result와 toast에 저장 경로를 남긴다. | report data가 없으면 파일을 만들지 않는다. | 없음 |
| `/save` | Textual workflow는 자동 저장된다는 안내를 modal/toast로 표시한다. | central result에 자동 저장 안내를 남긴다. | plain TUI의 session history 저장과 혼동하지 않게 문구를 분리한다. | 없음 |
| `/rounds` | 현재 값을 설정 modal에 표시한다. | central result에 현재 값을 남긴다. | 없음 | 없음 |
| `/rounds N` | 현재 세션 값만 바꾸고 결과를 표시한다. | central result에 변경 결과와 config 파일 미저장 안내를 남긴다. | 범위 밖이면 `1..20` usage 오류를 표시한다. | 없음 |
| `/agent` | agent 목록과 enable 상태를 modal로 표시한다. | central result에 agent 목록과 usage를 남긴다. | 알 수 없는 agent면 후보를 표시한다. | 없음 |
| `/agent name on/off` | 현재 세션 agent 상태를 바꾸고 결과를 표시한다. | central result에 변경 결과와 config 파일 미저장 안내를 남긴다. | 잘못된 action은 usage 오류를 표시한다. | 없음 |
| `/caveman` | 현재 compression 상태와 강도를 modal로 표시한다. | central result에 현재 상태를 남긴다. | 없음 | 없음 |
| `/caveman mode` | 현재 세션 compression 상태를 변경하고 결과를 표시한다. | central result에 변경 결과와 config 파일 미저장 안내를 남긴다. | 잘못된 mode는 usage 오류를 표시한다. | 없음 |
| `/target` | 현재 target/candidate와 기본 workspace를 modal로 표시한다. | central result에 현재 target을 남긴다. | target이 없으면 `/target <path>`와 Choose flow를 안내한다. | 없음 |
| `/target path` | workspace guardrail 확인 후 target을 설정한다. | central result에 설정 결과를 남긴다. | control repo 내부 path는 확인 없이 허용하지 않는다. | 없음 |
| `/target clear` | target 제거 결과를 표시한다. | central result에 제거 결과를 남긴다. | 없음 | 없음 |
| `/resume` | archive selector modal을 연다. | archive selector modal을 연다. | archive가 없으면 empty message를 표시한다. | 없음 |
| `/resume selector` | matching archive를 active session으로 복원하고 Nexus로 이동한다. | matching archive를 active session으로 복원하고 snapshot을 갱신한다. | matching archive가 없으면 오류를 표시한다. | 없음 |
| `/execute` | blueprint가 없으므로 실행하지 않고 안내한다. | blueprint/target 조건을 검사하고 실행 preflight로 이동한다. | blueprint 없으면 안내, target 없으면 workspace picker를 연다. | execution |
| `/quit`, `/exit`, `/q` | 종료 확인 modal을 표시한다. | 종료 확인 modal을 표시한다. | running worker가 있으면 더 강한 확인 문구를 표시한다. | 없음 |
| unknown `/...` | unknown command modal/toast를 표시하고 입력을 비운다. | central result에 unknown command 오류를 남긴다. | 유사 command 후보가 있으면 함께 표시한다. | 없음 |

## 구현 순서

### 1. 공통 result model 정리

- `LocalCommandSnapshot`에 result kind를 추가한다.
- message, markdown, table, path, action hint를 같은 구조로 전달한다.
- Start modal과 Nexus central result가 같은 snapshot을 다르게 렌더링하게 만든다.

### 2. Start modal 표준화

- `/help`, `/workflow`, `/decisions`, `/packages`, `/subtasks`, `/history`용 generic local command modal을 만든다.
- `/status`, `/context` 전용 modal은 generic modal로 통합 가능한지 검토한다.
- empty state는 modal 본문 또는 짧은 toast 중 command별 계약을 따른다.

### 3. Nexus central result 표준화

- local command result가 command별로 교체될지 누적될지 정책을 명확히 한다.
- read-only table은 cursor/selection을 비활성화한다.
- result title은 버튼처럼 보이지 않게 유지한다.

### 4. 조회 명령 일괄 보강

- `/help`, `/workflow`, `/questions`, `/decisions`, `/packages`, `/subtasks`, `/history`, `/report`를 먼저 정리한다.
- 모든 조회 명령은 Start/Nexus에서 에이전트 호출이 없어야 한다.

### 5. 설정 명령 일괄 보강

- `/rounds`, `/agent`, `/caveman`의 no-arg 상태 표시와 arg 변경 결과를 같은 UI 계약으로 맞춘다.
- config 파일 미저장 안내를 공통 문구로 유지한다.

### 6. workflow-local 명령 보강

- `/target`, `/resume`, `/questions --select`를 picker/modal 중심으로 정리한다.
- `/answer`는 질문 영역과 decision ledger를 함께 갱신한다.

### 7. 실행/종료/unknown 마감

- `/execute`의 blueprint/target/running state별 메시지를 고정한다.
- `/quit` alias는 종료 확인 UX를 통일한다.
- unknown command는 후보 추천을 추가한다.

## 회귀 테스트 기준

모든 command는 최소 다음 축으로 검증한다.

| 테스트 축 | 검증 내용 |
| :--- | :--- |
| Start routing | `start_prompt()`가 호출되지 않고 Start에 머문다. |
| Nexus routing | `submit_follow_up()`이 호출되지 않고 central result 또는 picker가 열린다. |
| Empty state | 데이터가 없을 때 조용히 실패하지 않고 메시지가 보인다. |
| Result surface | Start는 modal/toast, Nexus는 central result를 따른다. |
| Input cleanup | command 실행 후 composer 입력이 비워진다. |
| Agent policy | registry의 `agent_call` 정책과 실제 worker 호출 여부가 일치한다. |
| Table read-only | read-only table은 선택/클릭 가능해 보이지 않는다. |
| File side effect | 파일 기록 명령은 성공 시 경로를 남기고 실패 시 파일을 만들지 않는다. |

## 완료 기준

- 이 문서의 명령별 UX 계약이 `docs/slash-command-reference.md`와 충돌하지 않는다.
- `tests/test_slash_command_docs.py`가 registry와 문서 command set 불일치를 잡는다.
- Textual Start/Nexus의 모든 Trinity slash command에 대해 에이전트 호출 금지/허용 정책 테스트가 있다.
- 사용자가 `/` 명령을 실행했을 때 "아무 반응 없음" 상태가 없어야 한다.
- Start와 Nexus에서 같은 명령의 결과 표현이 의도적으로 다를 뿐, 데이터 기준은 같아야 한다.
