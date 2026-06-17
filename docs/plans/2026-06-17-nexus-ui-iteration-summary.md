# Nexus UI Iteration Summary and Next Work

작성일: 2026-06-17

기준 브랜치: `feature/nexus-progress-visibility`

상태: 병합 전 최종 정리

## 목적

이 문서는 직전 브랜치 `feature/nexus-conversation-ux`와 이번 브랜치
`feature/nexus-progress-visibility`에서 Nexus UI에 반영한 변경사항을 묶어 기록하고,
다음 구현 라운드에서 이어갈 작업을 정리한다.

두 브랜치의 공통 목표는 Nexus를 "내부 상태 덤프"가 아니라 사용자가 현재 상황을 판단하고 다음 행동을
고를 수 있는 작업면으로 만드는 것이다.

## 직전 브랜치: `feature/nexus-conversation-ux`

PR: `#65`

### 문제

기존 Nexus 중앙 영역은 다음 항목이 한 스크롤에 섞여 있었다.

- workflow id/state/round 같은 내부 메타데이터
- central blueprint 원문
- Architecture, Data Flow, Risks, Acceptance Criteria 같은 상세 설계 섹션
- work package 전체 목록
- decisions, subtasks, local policy repairs
- local command 결과
- 질문/답변 버튼

이 구조에서는 사용자가 "중앙 에이전트가 지금 무슨 판단을 했는지"와 "내가 무엇을 눌러야 하는지"를
빠르게 이해하기 어려웠다.

### 반영 내용

- `QuestionPanel`을 추가해 질문/답변 UI를 중앙 대화에서 분리했다.
- `CentralAgentView`를 progress, goal, compact central response, compact work package overview, action 중심으로 축소했다.
- 중앙 응답에서 다음 상세 섹션을 잘라내고 요약부만 보여주도록 했다.
  - `Architecture`
  - `Data Flow`
  - `External Dependencies`
  - `Risks`
  - `Acceptance Criteria`
  - `Work Packages`
  - `권장 사항`
  - `핵심 근거`
- 중앙 Work Packages 영역은 개별 WP 전체 목록을 숨기고 패키지 수와 상태 요약만 표시하도록 했다.
- local command table은 최신 명령 하나만 중앙에 렌더하도록 했다.
- `/questions` 안내 문구를 `question panel` 기준으로 수정했다.

### 사용자 관점 결과

Nexus 중앙은 이제 다음 정보만 우선적으로 보여준다.

- 현재 진행 상태
- 사용자 목표
- 중앙 에이전트의 짧은 응답
- 작업 패키지 개수/상태 요약
- 다음 액션 버튼
- 최신 local command 결과

질문은 별도 패널에 표시되므로, 중앙 응답과 사용자 결정 영역이 뒤섞이지 않는다.

## 이번 브랜치: `feature/nexus-progress-visibility`

### 문제

직전 브랜치 이후에도 "지금 무엇이 돌아가고 있는지"는 충분히 선명하지 않았다.

- provider card가 세로로 길고 상단 공간을 많이 차지했다.
- provider status가 `Running · Enabled`처럼 긴 원문 중심이라 시각적 구분이 약했다.
- 우측 Inspector의 `Packages`는 단순 목록이라 current/next/blocked를 빠르게 볼 수 없었다.
- 중앙 Work Packages 요약은 패키지 수 중심이라 execution 단계의 진행률을 한눈에 보기 어려웠다.

### 반영 내용

- provider card를 compact UI로 전환했다.
- provider strip/card 높이를 `8`에서 `5`로 줄였다.
- provider status를 짧은 상태 라벨로 정규화했다.
  - English: `RUN`, `WAIT`, `IDLE`, `DONE`, `ISSUE`, `OFF`
  - Korean: `실행`, `대기`, `휴식`, `완료`, `문제`, `끔`
- provider 상태별 class를 추가했다.
  - `provider-state-running`
  - `provider-state-waiting`
  - `provider-state-idle`
  - `provider-state-done`
  - `provider-state-issue`
  - `provider-state-off`
- `progress_summary.py`를 추가해 WP 진행 상태 계산을 공통 helper로 분리했다.
- 우측 `WorkflowInspector` 상단에 다음 섹션을 추가했다.
  - `Progress`
  - `Current`
  - `Next`
  - `Blocked`
- 기존 Inspector의 `Packages` 단순 리스트는 current/next/blocked 중심 표시로 대체했다.
- 중앙 Work Packages 요약에도 progress count, current 1개, blocked 1개를 보여주도록 보강했다.

### 사용자 관점 결과

Nexus에서 사용자는 다음을 빠르게 확인할 수 있다.

- 어떤 provider가 실행 중인지
- 어떤 provider가 대기/완료/문제 상태인지
- 전체 WP 중 몇 개가 완료/실행/대기/막힘인지
- 현재 실행 중인 WP가 무엇인지
- 다음 대기 WP가 무엇인지
- 막힌 WP와 간단한 이유가 무엇인지

## 검증 기록

이번 브랜치 기준으로 다음 테스트를 통과했다.

```text
uv run pytest tests/test_provider_panel.py tests/test_progress_summary.py tests/test_central_agent_view.py -q
20 passed

uv run pytest tests/test_textual_app.py -q
123 passed

uv run pytest tests/test_textual_snapshot.py tests/test_textual_workflow_controller.py tests/test_textual_smoke.py -q
66 passed
```

## 다음 작업

### 1. `Next` WP를 dependency-ready 기준으로 고도화

현재 `Next`는 `pending`, `queued`, `waiting` 상태를 단순 후보로 보여준다. 실제로 바로 실행 가능한 WP인지,
선행 dependency가 끝났는지는 계산하지 않는다.

다음 단계에서는 다음 기준을 적용해야 한다.

- dependencies가 모두 `done`인 pending WP를 먼저 보여준다.
- dependency가 남은 WP는 `Waiting on WP-xxx`처럼 표시한다.
- 병렬 실행 가능한 WP 그룹이 있다면 같은 그룹을 함께 보여준다.

### 2. 실제 TUI 화면 QA

자동 테스트는 통과했지만, Textual UI는 실제 터미널 폭/높이에 따라 체감이 달라진다.

확인할 항목:

- provider card가 너무 낮아 글자가 잘리지 않는지
- `Antigravity`처럼 긴 provider 이름이 좁은 카드에서 깨지지 않는지
- 한국어 상태 라벨이 provider card 안에서 잘 맞는지
- Inspector 상단 섹션이 너무 많아져 핵심 정보가 다시 묻히지 않는지
- `Progress` bar가 작은 터미널에서도 읽히는지

### 3. Provider card model/session 정보 보강

현재 provider card는 provider id와 summary 위주다. 모델 선택 기능과 연결해 다음 정보를 더 깔끔하게 표시할 수 있다.

- 현재 선택 모델
- provider-native session id 축약값
- context/budget 상태

단, card를 다시 장황하게 만들지 않도록 상세는 Provider Inspector에 남기고 card에는 1줄만 표시해야 한다.

### 4. Inspector 상세 정보 탭화 검토

Inspector가 계속 섹션이 늘어나면 다시 복잡해질 수 있다. 다음 중 하나를 검토한다.

- Inspector 안에서 `Overview`, `Details`, `Log` 탭 분리
- `Decisions`, `Execution Log`를 접힌 형태로 표시
- `Current/Next/Blocked`만 항상 상단 고정

### 5. Execution Matrix와 Nexus 상태 표현 통일

Execution Matrix의 status/review/progress 표현과 Nexus의 `RUN/WAIT/DONE/ISSUE` 표현이 달라지면 사용자 혼란이 생길 수 있다.

다음 작업에서는 상태 라벨 mapping을 공유하거나 문서화해야 한다.

### 6. PR 후 실제 사용자 시나리오 재검증

병합 후 다음 시나리오를 한 번 더 확인한다.

1. 새 prompt 입력
2. blueprint ready 확인
3. execute preflight
4. WP 실행 중 Nexus 이동
5. WP 완료/blocked/reviewing 상태 확인
6. `/execute-retry` 또는 review repair 상태와 Nexus progress 표시가 일치하는지 확인

## 남은 리스크

- 현재 progress summary는 Textual UI projection에서 계산하므로 workflow engine의 실제 scheduling readiness와 완전히 같지는 않다.
- status 문자열이 새 provider 상태에서 추가되면 `progress_summary.py`와 `provider_panel.py` mapping 보강이 필요하다.
- provider card compact화로 summary 정보량은 줄었다. 원문 확인 경로인 Provider Inspector가 계속 안정적으로 동작해야 한다.

