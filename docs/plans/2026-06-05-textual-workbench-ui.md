# Textual Workbench UI/UX Redesign

- Date: 2026-06-05
- Target version: 0.10.0
- Status: planning
- Scope: Trinity 기본 실행 화면을 Textual 기반 desktop-app 스타일 workbench로 재설계한다.

## 배경

현재 Trinity의 기본 대화형 실행은 Rich Live와 prompt_toolkit 입력 루프를 조합한다. 이 구조는 가볍고 안정적이지만, 사용자가 기대하는 "앱처럼 동작하는" UI에는 한계가 있다.

- 입력창이 단일 줄 중심이라 긴 요구사항 작성, 줄바꿈, 선택, 붙여넣기 UX가 제한된다.
- agent 응답이 통합 출력 중심이라 Claude, Codex, Antigravity 의견을 독립적으로 비교하기 어렵다.
- planning과 execute가 UI상 명확히 분리되어 있지 않아, 어느 시점에 실제 작업 디렉토리와 파일 변경 권한이 필요한지 사용자에게 덜 선명하다.
- 테마는 런타임 설정 표면이 작고, 사용자가 나중에 앱 안에서 바꾸기 어렵다.

목표는 Trinity를 채팅 CLI가 아니라 agent workbench로 보이게 만드는 것이다. 사용자는 요구사항을 작성하고, 여러 agent의 의견과 중앙 synthesis를 비교하고, 합의된 blueprint를 검토한 뒤, execute 시점에만 작업 디렉토리와 실행 권한을 선택한다.

## 설계 원칙

1. Planning은 안전해야 한다.
   - 사용자가 일반 프롬프트를 입력하는 단계에서는 작업 디렉토리를 묻지 않는다.
   - planning, 합의, 질문, blueprint 생성은 기본적으로 파일 변경 없이 진행한다.

2. Execute는 명시적이어야 한다.
   - 실제 파일 변경 또는 명령 실행은 사용자가 `Execute`를 선택한 뒤 시작한다.
   - 이 시점에 workspace picker, git 상태, 브랜치, provider readiness, 쓰기 권한을 preflight로 보여준다.

3. Agent 의견은 비교 가능해야 한다.
   - 각 agent 응답은 독립된 scroll surface를 가진다.
   - synthesis summary와 원문 응답을 분리해서 보여준다.

4. 입력은 문서 편집처럼 동작해야 한다.
   - multi-line 입력, 선택, 복사, 붙여넣기, 긴 텍스트 작성이 자연스러워야 한다.
   - slash command는 입력값이 `/`로 시작할 때만 command palette 또는 completion을 연다.

5. 설정은 앱 내부에서 수정 가능해야 한다.
   - 첫 구현 범위에서 Settings는 theme 설정을 중심으로 시작한다.
   - provider, workspace, execution policy 같은 위험한 설정은 별도 단계에서 추가한다.

## 정보 구조

기본 화면은 4개 영역으로 구성한다.

```text
┌ Trinity v0.10.0 ─ workflow: planning ─ transport: one-shot ─ agents: 3/3 ┐
│ Sidebar           │ Main Conversation / Synthesis         │ Inspector    │
│ - Sessions        │ - user prompt                          │ - Questions  │
│ - Agents          │ - synthesis summary                    │ - Decisions  │
│ - Workflows       │ - round timeline                       │ - Packages   │
│ - History         │                                       │ - Context    │
├───────────────────┴───────────────────────────────────────┴──────────────┤
│ Agent Responses                                                           │
│ [Claude] [Codex] [Antigravity] [All]                                      │
│ 각 agent 응답을 독립 스크롤 가능한 pane/tab으로 표시                       │
├───────────────────────────────────────────────────────────────────────────┤
│ Prompt Composer                                                           │
│ multi-line TextArea                                                       │
│ Enter: newline | Ctrl+Enter: send | /: command palette                    │
└───────────────────────────────────────────────────────────────────────────┘
```

### Sidebar

Sidebar는 navigation과 session awareness를 담당한다.

- Sessions: 현재 세션, resume 가능한 과거 workflow
- Agents: 활성 agent, provider, readiness
- Workflows: 현재 workflow state와 round
- History: 저장된 blueprint, decisions, execution result
- Settings: 앱 설정 진입점

### Main

Main 영역은 사용자와 중앙 synthesis의 대화면이다.

- 사용자 prompt
- synthesis summary
- synthesis가 생성한 대화형 질문
- 선택지 또는 자유 입력 답변
- blueprint 상태
- execute 가능 여부

대화형 질문은 버튼/선택지와 free-form 답변을 모두 지원한다. 사용자가 선택지 대신 직접 텍스트를 입력할 수 있어야 한다.

### Agent Responses

Agent Responses 영역은 tabbed view로 시작한다.

- `Claude`
- `Codex`
- `Antigravity`
- `All`

각 tab은 독립 scroll 상태를 가진다. 넓은 화면에서는 3-column compare mode를 제공할 수 있고, 좁은 화면에서는 tabs만 유지한다.

각 응답 surface는 다음 상태를 표시한다.

- queued
- running
- responded
- failed
- timed out
- skipped

각 agent 응답에는 원문 보기와 요약 보기를 둔다. 요약은 synthesis 결과와 구분한다.

### Inspector

Inspector는 현재 workflow의 구조적 상태를 보여준다.

- Pending questions
- Decisions
- Work packages
- Subtasks
- Review packages
- Shared context
- Token/cost estimate
- Provider readiness

Inspector는 실행 버튼을 대신하지 않는다. 실행은 Main 하단 action bar 또는 Blueprint Ready 화면에서 명시적으로 시작한다.

### Prompt Composer

Prompt Composer는 Textual `TextArea` 기반으로 설계한다.

권장 키맵:

- `Enter`: 줄바꿈
- `Ctrl+Enter`: 전송
- `Esc`: composer focus 해제
- `/`: composer가 비어 있거나 첫 글자가 `/`일 때 command palette
- `Ctrl+V` / `Cmd+V`: 붙여넣기
- `Shift+Arrow`: 텍스트 선택
- `Ctrl+A`: composer 내부 전체 선택
- `Ctrl+C` / `Cmd+C`: 선택 텍스트 복사
- `Up` / `Down`: multi-line 내부 이동
- 빈 composer에서 `Up`: 입력 history 탐색

터미널별 clipboard 동작은 Textual과 터미널 emulator의 제약을 받는다. 지원 여부는 doctor 또는 Settings에서 표시한다.

## Workflow UX

### 1. Prompt 입력

사용자는 요구사항을 composer에 작성한다. 이 단계에서는 작업 디렉토리를 묻지 않는다.

결과:

- 새 workflow 생성
- active agents 확인
- one-shot provider 호출 준비
- shared context 초기화

### 2. Round 실행

각 agent가 병렬 또는 정책에 따른 순서로 응답한다.

UI:

- Agent tab별 running 상태 표시
- Round timeline 업데이트
- 응답 도착 시 해당 tab에 append
- synthesis가 전체 응답을 요약하고 질문/결론/다음 행동을 생성

### 3. 대화형 질문

synthesis가 사용자의 결정을 요구하면 Main에 질문 카드가 아니라 대화형 prompt block으로 표시한다.

지원 입력:

- 선택지 클릭 또는 키보드 선택
- 직접 텍스트 입력
- 보류
- 새 round 요청

질문 답변은 workflow ledger와 shared context에 기록한다.

### 4. Blueprint Ready

합의가 끝나면 blueprint ready 상태가 된다.

UI:

- 합의 요약
- 주요 결정
- work package 목록
- 위험/전제
- `Continue Planning`
- `Execute`
- `Save`

일반 텍스트 입력은 새 workflow를 시작하지 않고 현재 blueprint의 follow-up으로 분류한다. 새 workflow는 명시적인 `New Session` 액션으로 시작한다.

### 5. Execute

사용자가 `Execute`를 선택하면 이때 workspace picker를 연다.

Workspace picker:

- 현재 shell cwd
- 최근 선택 workspace
- git repo 후보
- 직접 경로 입력
- 폴더 유효성 검사

Preflight:

- 경로 존재 여부
- git repo 여부
- 현재 브랜치
- dirty worktree 여부
- 쓰기 권한
- provider readiness
- execution package 목록
- 병렬 실행 가능 여부

사용자가 승인하면 execution protocol을 시작한다.

## Settings와 Theme

0.10.0 설계에서 Settings는 theme 설정을 우선 범위로 둔다. 이는 안전한 설정이며, provider 인증이나 execution policy와 달리 즉시 바꿔도 작업 결과에 영향을 주지 않는다.

### Settings 진입점

- Sidebar의 `Settings`
- Command palette의 `/settings`
- 단축키 후보: `Ctrl+,`

### Theme 설정 범위

초기 theme 설정은 다음 항목만 포함한다.

- Theme mode: `system`, `dark`, `light`
- Color profile: `auto`, `truecolor`, `256color`, `ascii-safe`
- Density: `comfortable`, `compact`
- Motion: `normal`, `reduced`
- Unicode rendering: `auto`, `unicode`, `ascii`

설정은 즉시 preview되고, 사용자가 Apply를 누르면 저장한다.

저장 위치:

- project 설정이 아니라 사용자 UI preference로 저장한다.
- 후보 경로: `config.effective_state_dir / "ui" / "settings.toml"`
- provider state나 workflow ledger와 섞지 않는다.

### Theme preview

Settings 화면에는 작은 preview panel을 둔다.

- header
- agent status chip
- selected tab
- warning state
- code/text block
- action button

이를 통해 사용자가 현재 터미널에서 색상과 Unicode 렌더링이 실제로 어떻게 보이는지 확인할 수 있다.

### Settings 비범위

0.10.0 Textual UI 설계에서는 다음 설정은 제외한다.

- provider auth
- provider state mode
- execution permission policy
- workspace trust policy
- model routing
- synthesis mode

이 설정들은 이후 별도 settings section으로 확장하되, 초기 Settings에서는 theme만 다룬다.

## 화면 크기 대응

### Wide

- Sidebar + Main + Inspector
- Agent Responses 3-column compare mode 선택 가능

### Medium

- Sidebar 접기 가능
- Main + Inspector
- Agent Responses는 tabs

### Narrow

- Sidebar drawer
- Inspector drawer
- Main 단일 column
- Agent Responses tabs
- Composer 고정

## 구현 방향

기존 orchestration, workflow, provider invocation은 유지한다. 새 UI는 presentation/input 계층으로 추가한다.

신규 후보 패키지:

- `src/trinity/textual_app/app.py`
- `src/trinity/textual_app/screens/main.py`
- `src/trinity/textual_app/screens/settings.py`
- `src/trinity/textual_app/widgets/composer.py`
- `src/trinity/textual_app/widgets/agent_tabs.py`
- `src/trinity/textual_app/widgets/inspector.py`
- `src/trinity/textual_app/widgets/workspace_picker.py`
- `src/trinity/textual_app/theme.py`
- `src/trinity/textual_app/settings.py`

기존 Rich TUI는 fallback으로 유지한다.

- `trinity --plain`: 기존 prompt_toolkit/Rich session
- `TRINITY_TUI=plain`: 강제 fallback
- Textual import 실패 시 plain fallback

## 구현 순서

1. Textual 의존성 추가와 feature flag 도입
2. Textual app shell 생성
3. Prompt Composer 구현
4. Workflow event bridge 구현
5. Agent Responses tabs 구현
6. Main synthesis view 구현
7. Inspector 구현
8. Settings theme 화면 구현
9. Execute workspace picker 구현
10. CLI 기본 진입점을 Textual로 전환하고 plain fallback 유지
11. 스냅샷/단위 테스트와 cross-platform smoke 갱신
12. README와 troubleshooting 문서 갱신

## Acceptance Criteria

- `trinity` 실행 시 Textual workbench가 기본으로 열린다.
- 긴 프롬프트를 multi-line으로 작성하고 `Ctrl+Enter`로 보낼 수 있다.
- `/` completion은 slash command 입력에서만 열린다.
- 각 agent 응답은 독립적으로 스크롤할 수 있다.
- synthesis 질문은 선택지와 자유 입력을 모두 지원한다.
- planning 단계에서는 작업 디렉토리를 묻지 않는다.
- `Execute` 시점에 workspace picker와 preflight가 열린다.
- Settings에서 theme 설정을 변경하고 저장할 수 있다.
- plain fallback으로 기존 TUI를 사용할 수 있다.

## Open Questions

- Textual clipboard 기능이 Windows Terminal, PowerShell, macOS Terminal에서 어느 수준까지 일관적인지 smoke가 필요하다.
- Theme preference를 global user config에 둘지 project-local state에 둘지 최종 결정이 필요하다.
- Agent Responses의 3-column compare mode를 0.10.0에 포함할지, tabs만 먼저 구현할지 결정이 필요하다.
- `Ctrl+Enter`가 일부 terminal에서 구분되지 않을 경우 대체 전송 키를 무엇으로 둘지 검증이 필요하다.
