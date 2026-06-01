# Trinity Phase 6 — Interactive Setup + Terminal UI

> 2026-06-01 사용자 피드백 기반 기획

---

## 6-1. 인터랙티브 초기 설정 (`trinity init` 개선)

### 문제
현재 `trinity init`은 Claude/Codex/Gemini를 자동 감지하지 않고 기본값으로만 생성한다.
사용자가 어떤 CLI가 설치되어 있는지, 어떤 에이전트를 활성화할지 직접 결정해야 한다.

### 개선 방향

```
$ trinity init

🔍 Detecting AI CLI tools...

  ✅ Claude Code  (claude v1.0.0)   — detected
  ✅ Codex CLI    (codex v0.1.0)    — detected  
  ❌ Gemini CLI   (gemini)          — not found

Which agents do you want to enable? [claude, codex]:
> claude, codex

📋 Agent Configuration

  Claude Code:
    Role: Architect (default) → 
    Context budget: 200,000 tokens

  Codex:
    Role: Implementer (default) → 
    Context budget: 128,000 tokens

💾 Saving config to .trinity/trinity.config...

✓ Trinity initialized!
  Agents: claude (active), codex (active)
  Gemini: skipped (CLI not installed)

💡 To add Gemini later:
   1. Install: https://github.com/google-gemini/gemini-cli
   2. Run: trinity config agents.gemini.enabled true
```

### 구현 항목

| 작업 | 상세 |
|------|------|
| **CLI 자동 감지** | `claude --version`, `codex --version`, `gemini --version` 실행하여 설치 여부/버전 확인 |
| **인터랙티브 에이전트 선택** | 감지된 CLI 중 활성화할 에이전트 선택 (Rich checkbox) |
| **역할 프롬프트 커스터마이징** | 기본 역할(Architect/Implementer/Reviewer) 제안 후 사용자 수정 가능 |
| **Context budget 자동 감지** | Provider별 기본값 적용, 사용자 수정 가능 |
| **미설치 CLI 안내** | 설치 방법 URL + 나중에 추가하는 방법 안내 |
| **기존 설정 감지** | 이미 `.trinity/`가 있으면 마이그레이션 옵션 제공 |

---

## 6-2. Terminal UI (`trinity` 단독 실행)

### 문제
현재 `trinity`만 실행하면 도움말만 나온다.
사용자는 Claude CLI처럼 **인터랙티브 프롬프트**에서 직접 질문하고 결과를 보고 싶다.

### 목표 UI

```
$ trinity

╭─────────────────────────────────────────────────────────────╮
│                    🧠 Trinity v0.1.1                        │
│              Three minds, one context                       │
│                                                             │
│  Agents: claude ✅  codex ✅  gemini ❌                     │
│  Session: trinity-session                                   │
╰─────────────────────────────────────────────────────────────╯

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📊 Agent Status                    Round: 2/5  ⏱ 1m 23s
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ┌─ Claude (Architect) ───────────────────── context: 32% ─┐
  │ 💬 "pytest를 기본 프레임워크로 추천합니다..."            │
  │ 📊 Status: RESPONDED                                    │
  └─────────────────────────────────────────────────────────┘

  ┌─ Codex (Implementer) ─────────────────── context: 18% ──┐
  │ 💬 "동의합니다. pytest가 가장 널리 쓰입니다..."           │
  │ 📊 Status: RESPONDED                                    │
  └─────────────────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📋 Deliberation Progress
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Round 1: ✅ Claude 응답 → ✅ Codex 응답 → 합의 판정중...
  Round 2: 🔄 진행중...

  Consensus: ⏳ 대기 (1/2 동의)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  💬 trinity> 파이썬 프로젝트 테스트 전략을 알려줘          │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 화면 구성 요소

| 영역 | 설명 |
|------|------|
| **헤더** | Trinity 버전, 활성 에이전트 목록, 세션 정보 |
| **에이전트 상태 패널** | 각 에이전트의 현재 응답 요약, context 사용량, 상태(RESPONDING/IDLE/ERROR) |
| **토론 진행 패널** | 라운드 진행 상황, 합의 판정 결과, 타임라인 |
| **입력 프롬프트** | 사용자 질문 입력 (하단 고정) |

### 구현 항목

| 작업 | 기술 | 상세 |
|------|------|------|
| **TUI 프레임워크** | Textual 또는 Rich Live | 터미널 UI 렌더링 |
| **에이전트 상태 실시간 업데이트** | asyncio + 큐 | 에이전트 응답 스트리밍을 UI에 반영 |
| **사용자 입력 프롬프트** | Rich Prompt / Textual Input | 하단에 `trinity>` 프롬프트 표시 |
| **라운드 진행 시각화** | Rich Progress | 각 라운드별 에이전트 응답 상태 표시 |
| **합의/분담 결과 패널** | Rich Panel | 합의 도달 시 요약 + 작업 분담 테이블 |
| **명령어 모드** | `/status`, `/context`, `/quit` | 프롬프트에서 내부 명령어 지원 |
| **tmux 연동** | tmux pane 분할 | 각 에이전트를 별도 pane에서 실행, UI는 메인 pane |

### tmux 레이아웃

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│              Trinity TUI (상태/입력)                     │
│                                                         │
├────────────────────────┬────────────────────────────────┤
│                        │                                │
│    Claude (Architect)  │    Codex (Implementer)         │
│    [터미널 출력]        │    [터미널 출력]                │
│                        │                                │
├────────────────────────┴────────────────────────────────┤
│  💬 trinity>                                            │
└─────────────────────────────────────────────────────────┘
```

- **상단**: Trinity TUI — 전체 상태 대시보드 + 사용자 입력
- **하단 좌/우**: 각 에이전트의 실제 CLI 출력 (tmux pane)
- 사용자는 상단 TUI에서 질문 입력 → 하단 pane에서 에이전트 작업 실시간 관찰

---

## 6-3. 명령어 모드 (TUI 내부)

TUI 프롬프트에서 지원하는 명령어:

| 명령어 | 설명 |
|--------|------|
| `질문 텍스트` | 에이전트에게 토론 주제 전달 |
| `/status` | 에이전트 상태 테이블 표시 |
| `/context` | 공유 컨텍스트(shared.md) 표시 |
| `/rounds [N]` | 최대 라운드 수 변경 |
| `/agent <name> on/off` | 특정 에이전트 활성화/비활성화 |
| `/history` | 이전 토론 기록 표시 |
| `/save` | 현재 세션 결과 저장 |
| `/quit` 또는 `Ctrl+C` | 종료 |

---

## 구현 우선순위

```
Phase 6-A: trinity init 인터랙티브 설정 (CLI 감지 + 선택)
Phase 6-B: trinity TUI 기본 프레임 (Rich Live + 입력 프롬프트)  
Phase 6-C: tmux 레이아웃 연동 (에이전트 pane + TUI pane)
Phase 6-D: 실시간 상태 업데이트 + 합의/분담 시각화
Phase 6-T: 테스트
```

---

## 기술 스택 후보

| 항목 | 후보 1 | 후보 2 |
|------|--------|--------|
| TUI 프레임워크 | **Textual** (Rich 기반, async 지원) | Rich Live (가벼움) |
| 입력 처리 | Textual Input 위젯 | prompt_toolkit |
| 레이아웃 | tmux split-window | Textual CSS 레이아웃 |
| 의존성 | `textual>=0.40` | `rich>=13.0` (기존) |

---

*작성일: 2026-06-01*
*출처: 사용자 피드백 — Phase 6 기획*
