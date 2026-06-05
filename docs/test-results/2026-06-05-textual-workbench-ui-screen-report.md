# Textual Workbench UI Screen Report

- Date: 2026-06-05
- Branch: `feature/textual-workbench-ui`
- Target version: `0.10.0`
- Scope: `uv run trinity` 기본 Textual workbench UI 구성과 각 화면의 역할을 보고한다.

## 목적

이번 브랜치는 Trinity의 기본 대화형 실행을 기존 Rich/prompt_toolkit 기반 TUI에서 Textual 기반 workbench UI로 전환한다. 목표는 사용자가 첫 요구사항을 작성하고, Claude/Codex/Antigravity의 의견을 비교하고, 중앙 synthesis를 검토한 뒤, 실제 실행 단계에서만 workspace를 확정하는 흐름을 명확히 만드는 것이다.

## 전체 화면 구조

Textual workbench는 다음 화면과 modal로 구성된다.

1. Start Screen
2. Nexus Screen
3. Provider Inspector Modal
4. Workspace Picker / Execute Preflight Modal
5. Execution Matrix Screen
6. Settings Screen

화면 이동은 앱 전역 key binding과 화면별 action button으로 제공된다. 기본 route는 Start Screen이고, 사용자가 prompt를 제출하면 Nexus Screen으로 이동한다.

## 1. Start Screen

### UI 구성

Start Screen은 앱 시작 시 처음 보이는 화면이다.

구성 요소:

- Header: `Trinity - v0.10.0`
- 중앙 shell: `TRINITY` title, subtitle, prompt composer, workspace/action row
- Prompt composer: 첫 요구사항을 작성하는 multi-line 입력 영역
- Workspace candidate label: 현재 후보 workspace 표시
- `Choose now` button: planning 전에 workspace 후보를 선택하려는 사용자를 위한 진입점
- `Plan first` button: workspace 선택 없이 planning을 시작하는 기본 흐름
- Footer: 사용 가능한 주요 key hint 표시

### 역할

Start Screen의 핵심 역할은 첫 요구사항 작성이다. 이 단계에서는 실제 파일 변경이나 provider 실행 workspace를 확정하지 않는다.

`Choose now`는 실행 대상 확정이 아니라 candidate selection이다. 사용자가 미리 workspace 후보를 잡고 싶을 때 사용한다. 최종 실행 workspace는 `Execute` 단계의 preflight에서 다시 확정한다.

`Plan first`는 workspace 없이 안전하게 planning을 시작한다. 문서 설계 기준으로 기본 추천 흐름이다.

### 최근 보완 사항

- Prompt composer를 중앙 shell 안에 배치하여 화면 좌측으로 밀리는 문제를 수정했다.
- Start Screen mount 시 composer에 자동 focus가 들어가도록 했다.
- `Enter`로 prompt 제출이 가능하게 했다.
- `Alt+Enter`는 multi-line 줄바꿈으로 유지했다.

## 2. Nexus Screen

### UI 구성

Nexus Screen은 planning workflow의 중심 화면이다.

구성 요소:

- Provider strip: Claude, Codex, Antigravity provider panel 3개
- Action bar: `Open Provider Inspector`, `Execute`
- Central Agent area: workflow 상태, goal, synthesis, decisions, work packages, questions
- Workflow Inspector: workflow id, questions, decisions, packages, execution log 요약
- Prompt composer: follow-up, 질문 답변, 방향 수정 입력 영역
- Footer: route/action key hint 표시

### Provider Panel 역할

각 provider panel은 provider의 현재 상태와 짧은 summary를 표시한다.

표시 항목:

- Agent name
- Provider runtime
- Status: `Queued`, `Running`, `Ready`, `Error`, `Disabled`
- Enabled/Disabled
- Short summary 또는 error summary

최근 보완으로 persisted response artifact를 읽어 provider 상태를 복원한다. 따라서 workflow가 `needs_user_decision` 상태로 멈춘 뒤 UI를 다시 열어도, 이미 응답을 완료한 provider는 `Ready`로 표시된다.

### Central Agent 역할

Central Agent는 provider 응답을 사용자가 이해할 수 있는 workflow 상태로 정리하는 영역이다.

표시 항목:

- Workflow id
- Workflow state
- Round number
- Goal
- Synthesis summary
- Decisions
- Work packages
- Questions for you

최근 보완으로 Central Agent 영역은 scrollable surface가 되었다. 질문과 선택지가 많거나 synthesis가 길어져도 영역 내부에서 스크롤할 수 있다.

### Questions for You

질문 선택지는 2열 grid로 배치한다. 기존 한 줄 horizontal button 배치는 긴 한국어 선택지가 잘려 읽기 어려웠기 때문에, 2열 구조로 변경했다.

각 button은 tooltip에 전체 label을 보관한다. 화면 폭이 좁아 button 내부 텍스트가 일부 줄어들더라도 hover 가능한 환경에서는 전체 선택지를 확인할 수 있다.

## 3. Prompt Composer와 Slash Command Palette

Prompt composer는 Start Screen과 Nexus Screen에서 공통으로 사용하는 입력 위젯이다.

### 역할

- 일반 prompt 제출
- Nexus follow-up 입력
- slash command 입력 및 선택
- multi-line 작성

### 주요 key

- `Enter`: send
- `Ctrl+Enter`: send fallback
- `Alt+Enter`: newline
- `/`: 입력이 slash로 시작할 때 command palette 표시
- `Up` / `Down`: command palette가 열려 있으면 command 선택 이동
- `Enter`: command palette가 열려 있으면 선택한 command를 composer에 채움

### 등록된 slash command

현재 등록된 command는 기존 plain TUI의 command 목록을 재사용한다.

- `/status`: provider와 workflow 상태 확인
- `/context`: shared context summary 확인
- `/rounds`: deliberation round 확인
- `/agent`: agent 관련 상태 확인
- `/history`: session history 확인
- `/save`: workflow 저장
- `/caveman`: concise reasoning mode 관련 command
- `/workflow`: workflow ledger 확인
- `/questions`: pending question 확인
- `/answer`: pending question 답변
- `/decisions`: 결정 사항 확인
- `/packages`: work package 확인
- `/subtasks`: subtask 확인
- `/resume`: 저장된 workflow resume
- `/execute`: execution preflight 진입
- `/target`: target workspace candidate 설정
- `/help`: command help
- `/quit`: Trinity 종료

## 4. Provider Inspector Modal

### UI 구성

Provider Inspector는 provider 원문 응답을 확인하는 modal이다.

구성 요소:
