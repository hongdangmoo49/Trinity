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

## Screen Architecture

Trinity의 Textual UI는 세 개의 주요 화면과 하나의 상세 모달로 구성한다.

1. Start Screen: 첫 요구사항 작성과 선택적 workspace preview
2. Nexus Screen: provider brainstorming, synthesis, 사용자 질의응답
3. Execution Matrix Screen: work package 실행과 실시간 로그
4. Provider Inspector Modal: provider 원문 응답 상세 보기

이 구조는 planning과 execute를 시각적으로 분리한다. 사용자는 앱 시작 직후 요구사항 작성에 집중하고, 실제 파일 변경은 Execution Matrix 진입 전에 명시적으로 승인한다.

## 1. Start Screen

Start Screen은 프로그램 시작 시 사용자가 첫 프롬프트를 작성하는 화면이다.

디자인 컨셉:

- 미니멀하고 중앙에 집중되는 구조
- 터미널의 어수선함을 줄이고 시작의 몰입감을 제공
- workspace 선택은 가능하지만 필수 절차처럼 보이지 않게 처리

레이아웃:

```text
┌───────────────────────────────────────────────────────────────────────────┐
│                                                                           │
│                      T R I N I T Y                                        │
│               Three minds, one context                                    │
│                                                                           │
│        ┌────────────────────────────────────────────────────────┐         │
│        │ What should Trinity work on?                           │         │
│        │                                                        │         │
│        │ multi-line TextArea                                    │         │
│        │                                                        │         │
│        └────────────────────────────────────────────────────────┘         │
│                                                                           │
│        Target workspace: Not selected                                     │
│        [Choose now] [Plan first]                                          │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

Workspace preview:

- `Choose now`를 누르면 DirectoryTree 기반 picker를 열 수 있다.
- 사용자가 선택하지 않아도 `Plan first`로 planning을 시작할 수 있다.
- 선택된 workspace는 "후보 target"일 뿐이며, execute 시점 preflight에서 다시 확정한다.
- Start Screen에서 workspace 선택을 요구하지 않는다.

DirectoryTree 사용 원칙:

- 초기 화면에 항상 큰 DirectoryTree를 노출하지 않는다.
- workspace를 미리 선택하고 싶은 사용자를 위해 modal 또는 접이식 side panel로 제공한다.
- DirectoryTree는 execute 대상 확정이 아니라 candidate selection으로 취급한다.

## 2. Nexus Screen

Nexus Screen은 Trinity의 핵심 화면이다. 3개 provider가 각자 사고하고, 중앙 synthesis agent가 이를 요약하여 사용자와 소통한다.

디자인 컨셉:

- Dashboard 형태
- 3개의 provider가 동시에 돌아가는 느낌을 시각적으로 제공
- 사용자가 "각 provider의 상태"와 "중앙 결론"을 동시에 파악하게 함

레이아웃:

```text
┌ Trinity v0.10.0 ─ Nexus ─ workflow: planning ─ transport: one-shot ┐
│ Claude                     │ Codex                     │ Antigravity │
│ Running / Ready / Error    │ Running / Ready / Error   │ Ready       │
│ short summary or keywords  │ short summary or keywords │ keywords    │
├────────────────────────────┴───────────────────────────┴────────────┤
│ Central Agent                                                        │
│ - synthesis summary                                                  │
│ - consensus progress                                                 │
│ - questions for the user                                             │
│ - blueprint status                                                   │
├──────────────────────────────────────────────────────────────────────┤
│ Prompt Composer                                                      │
│ Enter: newline | Ctrl+Enter: send | /: command palette               │
└──────────────────────────────────────────────────────────────────────┘
```

Provider panels:

- 각 provider panel은 status board 역할을 한다.
- 응답 생성 중에는 LoadingIndicator를 표시한다.
- 완료되면 `Ready` 상태와 아주 짧은 요약 또는 키워드만 표시한다.
- 원문 응답은 화면을 혼잡하게 만들지 않고 Provider Inspector Modal에서 확인한다.

Central Agent:

- RichLog 또는 Markdown 기반으로 synthesis summary를 렌더링한다.
- 합의 진행률, 남은 질문, 핵심 결정, blueprint readiness를 표시한다.
- synthesis가 사용자에게 묻는 질문은 선택지와 직접 입력을 모두 지원한다.

하단 Prompt Composer:

- Nexus Screen의 composer는 follow-up, 질문 답변, 방향 수정에 사용된다.
- 일반 텍스트 입력은 새 workflow를 시작하지 않고 현재 workflow의 follow-up으로 분류한다.
- 새 workflow는 명시적인 `New Session` 액션으로만 시작한다.

## 3. Execution Matrix Screen

Execution Matrix Screen은 consensus가 이루어지고 사용자가 execute를 승인한 뒤 진입하는 화면이다. 3개 provider 또는 실행 agent가 역할을 분담하여 실제 코드를 작성하거나 파일을 조작하는 과정을 보여준다.

디자인 컨셉:

- Monitoring room
- 구조화된 작업 표와 실시간 로그가 함께 보이는 실행 화면
- "지금 무엇이 어디서 실행되고 있는지"를 명확히 보여줌

진입 조건:

- blueprint ready
- 사용자가 `Execute` 선택
- workspace picker에서 target workspace 확정
- preflight 승인

레이아웃:

```text
┌ Trinity v0.10.0 ─ Execution Matrix ─ workspace: /path/to/repo ┐
│ Task                          │ Assignee     │ Status │ Risk   │
│ DB schema update              │ Claude       │ Done   │ Medium │
│ API integration               │ Codex        │ Run    │ Low    │
│ Review and validation         │ Antigravity  │ Queue  │ Low    │
├────────────────────────────────────────────────────────────────┤
│ Execution Log                                                   │
│ > package WP-001 started                                        │
│ > writing src/...                                               │
│ > running tests                                                 │
│ > package WP-001 done                                           │
└────────────────────────────────────────────────────────────────┘
```

상단 DataTable:

- `Task`
- `Assignee`
- `Status`
- `Risk`
- `Started`
- `Duration`

하단 RichLog:

- 선택된 task 또는 전체 execution log를 실시간 스트리밍한다.
- 파일 생성, 명령 실행, 테스트 결과, provider 응답 요약을 시간순으로 표시한다.
- 실패 시 blocker와 retry 가능 여부를 별도 강조한다.

## Provider Inspector Modal

Provider Inspector는 Nexus Screen에서 provider 원문 응답을 확인하는 상세 보기 modal이다.

사용 시점:

- 중앙 synthesis 요약만으로 충분하지 않을 때
- 특정 provider가 어떤 근거로 판단했는지 확인하고 싶을 때
- provider 원문 output을 비교하고 싶을 때

레이아웃:

```text
┌ Provider Inspector ─ Round 1 ───────────────────────────────────┐
│ [Claude] [Codex] [Antigravity] [All]                            │
├─────────────────────────────────────────────────────────────────┤
│ Raw provider output                                              │
│ Markdown rendered or plain raw view                              │
│ independent scroll                                               │
└─────────────────────────────────────────────────────────────────┘
```

동작:

- TabbedContent 기반 modal로 제공한다.
- 각 provider output은 독립 scroll을 가진다.
- `Raw`, `Cleaned`, `Summary` view toggle을 제공할 수 있다.
- modal은 읽기 전용이다.

## 정보 구조

Nexus Screen의 기본 workbench는 4개 영역으로 구성한다.

```text
┌ Trinity v0.10.0 ─ workflow: planning ─ transport: one-shot ─ agents: 3/3 ┐
│ Sidebar           │ Main Conversation / Synthesis         │ Inspector    │
│ - Sessions        │ - user prompt                          │ - Questions  │
│ - Agents          │ - synthesis summary                    │ - Decisions  │
│ - Workflows       │ - round timeline                       │ - Packages   │
│ - History         │                                       │ - Context    │
├───────────────────┴───────────────────────────────────────┴──────────────┤
│ Agent Summary / Inspector Entry                                           │
│ [Open Provider Inspector] [Compare Summaries]                             │
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

Agent Responses 원문은 기본 화면에 항상 펼쳐두지 않고 Provider Inspector Modal로 제공한다. 기본 Nexus Screen에서는 provider별 짧은 summary/status panel만 유지한다.

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

넓은 화면에서는 Provider Inspector를 modal 대신 docked panel로 열 수 있다. 좁은 화면에서는 반드시 modal/tabs를 사용한다.

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

사용자는 Start Screen 또는 Nexus Screen의 composer에 요구사항을 작성한다. 이 단계에서는 작업 디렉토리를 묻지 않는다.

결과:

- 새 workflow 생성
- active agents 확인
- one-shot provider 호출 준비
- shared context 초기화
- 선택된 workspace candidate가 있으면 session metadata로만 보관

### 2. Round 실행

각 agent가 병렬 또는 정책에 따른 순서로 응답한다.

UI:

- Nexus 상단 provider panel별 running 상태 표시
- Round timeline 업데이트
- 응답 도착 시 provider panel에 짧은 summary/keyword 표시
- 원문 응답은 Provider Inspector Modal에 저장
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

- Start Screen에서 선택한 workspace candidate
- 현재 shell cwd
- 최근 선택 workspace
- git repo 후보
- DirectoryTree 탐색
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

Execution Matrix Screen으로 전환한 뒤에는 work package DataTable과 execution RichLog가 주 화면이 된다.

## Visual Identity

Textual CSS를 사용해 Trinity의 시각적 정체성을 구성한다. 목표는 화려한 장식보다 provider별 역할과 상태가 즉시 읽히는 workbench다.

### Provider colors

각 provider에는 고유한 border와 accent color를 부여한다.

- Claude: soft violet / magenta 계열
- Codex: terminal green / success 계열
- Antigravity: blue / cyan 계열
- Central Agent: bright gray / white 계열의 굵은 border

색상은 식별 보조 수단이다. 접근성을 위해 상태 텍스트와 아이콘 또는 badge를 항상 함께 표시한다.

상태 badge 후보:

- `Queued`
- `Running`
- `Ready`
- `Needs Answer`
- `Error`
- `Timed Out`

### Consensus effect

합의가 도달하면 Central Agent 영역과 전체 app frame에 짧은 gold accent 효과를 줄 수 있다.

원칙:

- 기본 연출은 500ms 이하로 짧게 유지한다.
- `Motion: reduced` 설정에서는 애니메이션을 비활성화한다.
- 색상 변화만으로 의미를 전달하지 않고 `Consensus Reached` 텍스트를 함께 표시한다.

### Density

Trinity는 반복적으로 쓰는 개발 도구이므로 과한 hero/card 구성은 피한다.

- Start Screen만 중앙 집중형으로 둔다.
- Nexus와 Execution Matrix는 정보 밀도가 있는 dashboard 형태로 둔다.
- panel 안의 heading은 작고 명확하게 유지한다.

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
- `src/trinity/textual_app/screens/start.py`
- `src/trinity/textual_app/screens/nexus.py`
- `src/trinity/textual_app/screens/execution_matrix.py`
- `src/trinity/textual_app/screens/settings.py`
- `src/trinity/textual_app/widgets/composer.py`
- `src/trinity/textual_app/widgets/provider_panel.py`
- `src/trinity/textual_app/widgets/provider_inspector.py`
- `src/trinity/textual_app/widgets/inspector.py`
- `src/trinity/textual_app/widgets/workspace_picker.py`
- `src/trinity/textual_app/widgets/execution_table.py`
- `src/trinity/textual_app/theme.py`
- `src/trinity/textual_app/settings.py`

기존 Rich TUI는 fallback으로 유지한다.

- `trinity --plain`: 기존 prompt_toolkit/Rich session
- `TRINITY_TUI=plain`: 강제 fallback
- Textual import 실패 시 plain fallback

## 구현 순서

1. Textual 의존성 추가와 feature flag 도입
2. Textual app shell과 screen router 생성
3. Start Screen과 Prompt Composer 구현
4. Nexus Screen의 provider status panels 구현
5. Workflow event bridge 구현
6. Central Agent synthesis view 구현
7. Provider Inspector Modal 구현
8. Inspector와 workflow side surfaces 구현
9. Settings theme 화면 구현
10. Execute workspace picker와 preflight modal 구현
11. Execution Matrix Screen과 execution log stream 구현
12. CLI 기본 진입점을 Textual로 전환하고 plain fallback 유지
13. 스냅샷/단위 테스트와 cross-platform smoke 갱신
14. README와 troubleshooting 문서 갱신

## Acceptance Criteria

- `trinity` 실행 시 Textual workbench가 기본으로 열린다.
- Start Screen에서 큰 prompt composer를 중심으로 첫 요구사항을 입력할 수 있다.
- Start Screen workspace 선택은 optional이며 선택하지 않아도 planning이 진행된다.
- 긴 프롬프트를 multi-line으로 작성하고 `Ctrl+Enter`로 보낼 수 있다.
- `/` completion은 slash command 입력에서만 열린다.
- Nexus Screen에서 Claude, Codex, Antigravity provider panel이 상태와 짧은 summary를 보여준다.
- Provider Inspector Modal에서 각 agent 원문 응답을 독립적으로 스크롤할 수 있다.
- synthesis 질문은 선택지와 자유 입력을 모두 지원한다.
- planning 단계에서는 작업 디렉토리를 묻지 않는다.
- `Execute` 시점에 workspace picker와 preflight가 열린다.
- Execution Matrix Screen에서 work package DataTable과 execution log를 볼 수 있다.
- Settings에서 theme 설정을 변경하고 저장할 수 있다.
- plain fallback으로 기존 TUI를 사용할 수 있다.

## Open Questions

- Textual clipboard 기능이 Windows Terminal, PowerShell, macOS Terminal에서 어느 수준까지 일관적인지 smoke가 필요하다.
- Theme preference를 global user config에 둘지 project-local state에 둘지 최종 결정이 필요하다.
- Provider Inspector의 docked compare mode를 0.10.0에 포함할지, modal/tabs만 먼저 구현할지 결정이 필요하다.
- `Ctrl+Enter`가 일부 terminal에서 구분되지 않을 경우 대체 전송 키를 무엇으로 둘지 검증이 필요하다.
- Start Screen의 DirectoryTree 후보 선택을 modal로만 둘지, wide layout에서 side panel로도 노출할지 결정이 필요하다.
