# Nexus Conversation UX Redesign

작성일: 2026-06-16

브랜치: `feature/nexus-conversation-ux`

상태: 구현 반영

## 배경

현재 Nexus 중앙 영역은 대화 화면처럼 보이지만 실제로는 `WorkflowNexusSnapshot`을 고정 순서의
Markdown으로 다시 조립한 상태 덤프에 가깝다. 사용자가 입력한 질문과 중앙 에이전트의 응답, 질문/답변,
work package, 실행 결과, 결정 목록, local command 결과가 한 스크롤 안에 섞인다.

이 때문에 다음 문제가 생긴다.

- 질문/답변은 항상 중앙 Markdown 뒤에 붙어서 시간순 대화처럼 보이지 않는다.
- `Decisions`, `Subtasks`, `Local Policy Repairs`, 실행 로그성 요약이 중앙 영역에 노출되어 사용자가 읽기 어렵다.
- 진행 중 상태는 provider 카드와 중앙 제목의 작은 spinner 정도라 한눈에 현재 단계가 보이지 않는다.
- 중앙 영역이 "다음에 무엇을 할 수 있는지"보다 "내부 상태가 무엇인지"를 먼저 보여준다.

## 목표

1. Nexus 중앙 영역을 "중앙 에이전트와의 대화/작업면"으로 정리한다.
2. 질문/답변은 중앙 대화와 분리된 전용 영역에서 보여준다.
3. 사용자가 굳이 알 필요 없는 raw 상태, 내부 결정, repair note, local command detail은 중앙에서 제거한다.
4. 진행 중 상태를 단계와 카운트 중심으로 보여줘 현재 무엇이 돌아가는지 바로 알 수 있게 한다.
5. 기존 workflow, slash command, 질문 답변, blueprint action 동작은 유지한다.

## 비목표

- workflow/session 저장 포맷을 변경하지 않는다.
- 중앙 에이전트의 synthesis 정책이나 provider 호출 정책은 바꾸지 않는다.
- Inspector와 Report의 상세 정보 자체를 제거하지 않는다.
- 완전한 이벤트 타임라인 저장소를 새로 만들지 않는다.

## 현재 정보 흐름

`NexusScreen`은 다음 순서로 화면을 구성한다.

1. provider strip
2. action bar
3. central agent view + workflow inspector
4. agent/model target selector
5. composer

`CentralAgentView`는 현재 다음 정보를 한 Markdown에 조립한다.

- workflow id, state, round, synthesis progress
- goal
- synthesis summary
- central blueprint markdown
- central/local work package graph
- execution result summary
- local command results
- final review
- post-review follow-up items
- decisions
- subtasks
- local policy repairs

질문은 `central-questions` 컨테이너에 별도로 mount되지만 같은 중앙 스크롤의 마지막에 붙는다. 따라서
사용자가 "대화 순서"로 이해하기 어렵고, 질문/답변이 늘 화면 맨 아래로 밀린다.

## 새 UX 계약

### Central Conversation

중앙 대화 영역에는 다음만 보여준다.

- 현재 목표
- 중앙 에이전트 응답 또는 blueprint summary
- 현재 synthesis/실행 진행 요약
- 실행 가능한 다음 액션 버튼

중앙에서 제거할 항목:

- raw workflow id/state/round 라인
- 전체 decisions 목록
- subtasks 목록
- local policy repair 목록
- verbose execution result 목록
- local command body 전문
- 중복 WP graph 전문

상세 정보가 필요한 사용자는 우측 Inspector, Provider Inspector, Report, slash command 결과를 사용한다.

### Question Panel

질문/답변은 중앙 대화 아래의 별도 패널로 분리한다.

- 열린 질문은 상단에 강조 표시한다.
- 선택지는 2열 버튼 grid로 보여준다.
- 답변된 질문은 compact history로 남긴다.
- 질문이 없으면 패널은 짧은 "대기/질문 없음" 상태만 보여주거나 공간을 작게 쓴다.

### Progress Surface

중앙 영역 상단에는 현재 진행 단계를 짧게 보여준다.

- planning: provider 응답 수집/central synthesis
- ready: blueprint 준비, 실행 전
- executing: work package 진행 카운트
- reviewing/post-review: 리뷰와 보강 준비
- needs_user_decision: 사용자 답변 대기

진행 중이면 중앙 테두리와 상태 라벨을 함께 바꾼다.

### Inspector

우측 Inspector는 내부 상태와 상세 목록의 집으로 유지한다.

- workflow metadata
- provider model/session/context
- 질문 목록
- 결정 목록
- package 목록
- post review item
- 최근 execution log

중앙에서 제거된 정보는 Inspector 또는 Report에서 확인할 수 있어야 한다.

## 구현 계획

1. 새 `QuestionPanel` 위젯을 추가해 질문 렌더링과 버튼 이벤트를 담당하게 한다.
2. `NexusScreen`을 `CentralAgentView + QuestionPanel + Inspector` 구조로 바꾼다.
3. `CentralAgentView._markdown()`을 대화형 요약 중심으로 줄인다.
4. `CentralAgentView`에 progress/status summary helper를 추가한다.
5. 기존 질문 버튼 이벤트는 `QuestionPanel -> NexusScreen.QuestionAnswered`로 라우팅한다.
6. CSS를 조정해 중앙 대화, 질문 패널, 우측 Inspector가 시각적으로 분리되게 한다.
7. 기존 테스트를 새 역할에 맞게 갱신하고, 중앙에서 noisy section이 사라졌는지 테스트한다.

## 테스트 기준

- Central markdown에는 `### Decisions`, `### Subtasks`, `### Local Policy Repairs`, `### Local Command Results`가 나오지 않는다.
- blueprint ready 상태에서는 goal, central response, work package 요약, 다음 액션 버튼이 보인다.
- 질문 버튼은 `QuestionPanel`에서 렌더되고 기존 controller answer path로 라우팅된다.
- 답변된 질문은 버튼 없이 history로 남는다.
- 질문 옵션 grid는 2열을 유지한다.
- 진행 중 snapshot은 central running class와 progress line을 표시한다.
- slash command의 table 결과는 중앙이 아니라 local command summary/Inspector 경로에서 확인 가능해야 한다.

## 구현 결과

- `QuestionPanel` 위젯을 추가해 질문/답변 렌더링과 답변 버튼 이벤트를 중앙 대화에서 분리했다.
- `NexusScreen`은 좌측을 `CentralAgentView + QuestionPanel` 세로 스택으로 구성하고, 우측 Inspector는 유지한다.
- `CentralAgentView`는 workflow id/state/round, decisions, subtasks, local policy repairs, verbose execution result dump를 더 이상 중앙 Markdown에 노출하지 않는다.
- 중앙 대화는 progress line, goal, central response, compact work package overview, current focus, latest command result, final/post-review summary만 표시한다.
- local command table은 최신 명령 하나만 렌더해 오래된 명령 테이블이 중앙에 누적되지 않게 했다.
- `/questions` 안내 문구는 새 위치에 맞춰 `question panel`을 가리키도록 수정했다.

## 검증 결과

```text
uv run pytest tests/test_textual_app.py -q
123 passed in 68.49s (0:01:08)

uv run pytest tests/test_central_agent_view.py tests/test_textual_snapshot.py tests/test_textual_workflow_controller.py tests/test_textual_smoke.py -q
70 passed in 2.37s
```
