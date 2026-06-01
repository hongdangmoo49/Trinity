<div align="center">

◯ ─────────── ◯
# 🧠 T R I N I T Y
◯ ─────────── ◯

**세 개의 머리, 하나의 컨텍스트.**

**Claude Code** · **Codex** · **Gemini CLI** 세 AI 에이전트를
공유 컨텍스트, 라운드 기반 심의, 지능형 작업 분배로 통합하는
멀티 에이전트 AI 오케스트레이터.

[![License](https://img.shields.io/badge/license-MIT-green)](https://github.com/hongdangmoo49/Trinity/blob/main/LICENSE)
[![PyPI](https://img.shields.io/badge/PyPI-trinity--agent-blue)](https://pypi.org/project/trinity-agent/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-yellow)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-596%20passed-brightgreen)](https://github.com/hongdangmoo49/Trinity)

[English](./README.en.md) · [빠른 시작](#-빠른-시작) · [왜 Trinity인가](#-왜-trinity인가) · [작동 원리](#-작동-원리) · [TUI](#-인터랙티브-tui) · [명령어](#-명령어) · [아키텍처](#-아키텍처)

</div>

---

> **Trinity는 세 AI 코딩 에이전트를 하나의 협업 지능으로 통합합니다.**
>
> 한 AI에게 모든 걸 맡기는 대신, Trinity는 Claude(설계자), Codex(구현자), Gemini(검토자) 간의
> 구조화된 토론을 조율합니다. 세 에이전트가 컨텍스트를 공유하고, 라운드별로 토론하며,
> 합의에 도달한 뒤 각자의 강점에 따라 작업을 분배합니다.

---

## ❓ 왜 Trinity인가

단일 AI는 강력하지만, 맹점이 있습니다.

| 문제 | 발생 상황 | Trinity의 해결 |
| :--- | :--- | :--- |
| **터널 비전** | 한 AI가 한 가지 접근만 탐색 | 세 에이전트가 결정 전 대안을 토론 |
| **코드 리뷰 부재** | 설계 결함이 검증 없이 통과 | Gemini가 Claude의 설계를 검토·이의제기 |
| **컨텍스트 단절** | 각 에이전트가 고립되어 작업 | 공유 컨텍스트 파일로 모두가 같은 페이지 유지 |
| **불균형한 품질** | 코드 품질이 하나의 모델에 의존 | 합의 메커니즘이 교차 검증 보장 |
| **수동 위임** | 누가 뭘 할지 직접 결정해야 함 | 에이전트 강점에 따라 작업 자동 분배 |

---

## 🚀 빠른 시작

### 설치

```bash
pip install trinity-agent
```

### 프로젝트 초기화

```bash
# 인터랙티브 설정 위자드 — 설치된 AI CLI를 자동 감지합니다
trinity init

# 비인터랙티브 (기본값 사용)
trinity init --non-interactive
```

### 첫 심의 실행

```bash
# 원샷 질문
trinity ask "인증 시스템 아키텍처를 설계해줘"

# 인터랙티브 TUI 모드 (실시간 에이전트 토론)
trinity
```

Trinity가 자동으로 다음을 수행합니다:
1. 🔍 설치된 AI CLI 감지 (Claude Code, Codex, Gemini CLI)
2. 🧠 가용 에이전트 간 라운드 기반 심의 시작
3. 📊 합의, 작업 분배, 추론 과정과 함께 결과 표시

---

## 🔁 작동 원리

```
  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
  │   🏗️ Claude   │     │   ⚙️ Codex    │     │   🔍 Gemini   │
  │    (설계자)   │     │   (구현자)   │     │    (검토자)   │
  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
         │                   │                   │
         └───────────┬───────┴───────────────────┘
                     │
             ┌───────┴───────┐
             │   오케스트레이터 │
             │  공유 컨텍스트  │
             │    합의 엔진   │
             │   작업 분배기  │
             └───────────────┘
```

### 심의 플로우

| 단계 | 동작 |
| :--- | :--- |
| **초기화** | 목표와 에이전트 목록이 포함된 공유 컨텍스트(`shared.md`) 생성 |
| **라운드 1** | 각 에이전트가 사용자 요청에 대한 **초기 의견** 제시 |
| **라운드 2+** | 다른 에이전트의 의견을 읽고 **동의/비동의** 표명, 대안 제시 |
| **합의** | ≥60% 에이전트가 동의하면 합의 **도달** |
| **분배** | 각 에이전트의 **강점**에 따라 작업 자동 할당 |

### 에이전트 강점

| 에이전트 | 역할 | 특기 분야 |
| :--- | :--- | :--- |
| 🏗️ **Claude** | 설계자 (Architect) | 아키텍처, 설계, 코드 리뷰, 복잡한 로직, 기획 |
| ⚙️ **Codex** | 구현자 (Implementer) | 구현, 코딩, 프로토타이핑, 리팩토링, 테스트 |
| 🔍 **Gemini** | 검토자 (Reviewer) | 테스트, 연구, 대안 탐색, 엣지 케이스, 품질 보증 |

---

## 💬 인터랙티브 TUI

Trinity는 **Rich 기반 터미널 UI**로 실시간 심의 과정을 시각화합니다.

```
  🧠 Trinity v0.3.0  —  세 개의 머리, 하나의 컨텍스트

  🏗️ claude ✅    ⚙️ codex ✅    🔍 gemini ✅

  📊 에이전트 상태
  ┌──────────────────────────────────────────────────────────────────┐
  │  🏗️ claude    설계자      ✅ 응답완료     12%    pytest 추천... │
  │  ⚙️ codex     구현자      ✅ 응답완료      8%    동의함...      │
  │  🔍 gemini    검토자      ✅ 응답완료     15%    대안 제시...   │
  └──────────────────────────────────────────────────────────────────┘

  💬 심의 진행
  ─── 라운드 1 ─────────────────────────────────────────────────────
    ✅ claude (설계자)
    ┌──────────────────────────────────────────────────────────┐
    │  인증 시스템은 JWT(RS256) 기반을 추천합니다. 미들웨어   │
    │  패턴으로 아키텍처를 구성하면 확장성이 좋습니다...      │
    └──────────────────────────────────────────────────────────┘

    ✅ codex (구현자)
    ┌──────────────────────────────────────────────────────────┐
    │  claude에 동의합니다. 추가로 리프레시 토큰 회전을       │
    │  구현하면 보안이 강화됩니다...                           │
    └──────────────────────────────────────────────────────────┘

    ✅ gemini (검토자)
    ┌──────────────────────────────────────────────────────────┐
    │  OAuth2도 대안으로 고려해보세요. 토큰 회전 아이디어는   │
    │  좋지만 엣지 케이스 처리이 필요합니다...                │
    └──────────────────────────────────────────────────────────┘

    🔍 합의 판정중...  2/3 동의 (67%)

  💬 trinity>
```

### TUI 특징

- **실시간 스트리밍** — 모든 에이전트 완료 후가 아닌, 도착 즉시 의견 표시
- **에이전트별 고유 색상** — Claude(청록), Codex(초록), Gemini(자주)
- **Markdown 렌더링** — 에이전트 응답이 포맷팅 및 구문 강조로 표시
- **합의 진행률 바** — 동의 비율을 시각적 인디케이터로 표시
- **트리 작업 분배** — 누가 무엇을 하는지 명확한 트리 구조로 표시

---

## 📋 명령어

### CLI 명령어

| 명령어 | 설명 |
| :--- | :--- |
| `trinity` | 인터랙티브 TUI 세션 실행 |
| `trinity init` | 현재 디렉토리에 `.trinity/` 초기화 |
| `trinity init --non-interactive` | 기본값으로 초기화 (프롬프트 없음) |
| `trinity ask "질문"` | 프롬프트에 대해 원샷 심의 실행 |
| `trinity status` | 에이전트 상태 테이블 표시 |
| `trinity status-watch` | 실시간 업데이트 상태 대시보드 |
| `trinity context` | 공유 컨텍스트 표시 |
| `trinity config [키]` | 설정값 표시 |
| `trinity logs` | 오케스트레이터 로그 보기 |
| `trinity reset --keep-context` | 세션 초기화 (컨텍스트 보존) |
| `trinity attach` | tmux 세션에 연결 |

### TUI 인라인 명령어

인터랙티브 TUI 내부 (`trinity` 인자 없이 실행 시):

| 명령어 | 설명 |
| :--- | :--- |
| `<텍스트>` | 에이전트에게 주제 심의 요청 |
| `/status` | 에이전트 상태 표시 |
| `/context` | 공유 컨텍스트 표시 |
| `/rounds [N]` | 최대 심의 라운드 설정 (1–20) |
| `/agent <이름> on\|off` | 에이전트 활성화/비활성화 |
| `/history` | 심의 이력 표시 |
| `/save` | 세션 결과를 파일로 저장 |
| `/help` | 도움말 표시 |
| `/quit` | Trinity 종료 |

---

## ⚙️ 설정

`.trinity/trinity.config` 편집 (TOML 형식):

```toml
[general]
session_name = "trinity"
state_dir = ".trinity"
max_deliberation_rounds = 5
consensus_threshold = 0.6

[deliberation]
max_rounds = 5
consensus_threshold = 0.6
round_timeout_seconds = 120

[context]
rotate_threshold = 0.6
keep_sections = ["Current Goal", "Agreed Conclusion"]
recent_rounds_on_rotate = 3

[agents.claude]
provider = "claude-code"
cli_command = "claude"
role_prompt = "You are the Architect. You design systems, review code..."
enabled = true
extra_args = ["--dangerously-skip-permissions"]

[agents.codex]
provider = "codex"
cli_command = "codex"
role_prompt = "You are the Implementer. You write clean, efficient code..."
enabled = false                    # 기본 비활성화

[agents.gemini]
provider = "gemini-cli"
cli_command = "gemini"
role_prompt = "You are the Reviewer. You explore alternatives..."
enabled = false                    # 기본 비활성화
```

---

## 🏗️ 아키텍처

```
trinity/
├── orchestrator.py         # 최상위 코디네이터 — 모든 컴포넌트 소유
├── cli.py                  # Click 기반 CLI 진입점
├── config.py               # TOML 설정 로더 (기본값 포함)
├── models.py               # 핵심 데이터클래스 (AgentSpec, DeliberationMessage 등)
│
├── agents/                 # 프로바이더별 에이전트 래퍼
│   ├── base.py             #   AgentWrapper ABC
│   ├── claude_agent.py     #   Claude Code (print 모드 + 인터랙티브 tmux)
│   ├── codex_agent.py      #   Codex (print 모드 + 인터랙티브 tmux)
│   ├── gemini_agent.py     #   Gemini CLI (print 모드 + 인터랙티브 tmux)
│   └── factory.py          #   AgentFactory — 프로바이더별 에이전트 생성
│
├── deliberation/           # 토론 엔진
│   ├── protocol.py         #   라운드 기반 심의 루프 + 이벤트 스트리밍
│   ├── consensus.py        #   키워드 기반 합의 감지 + 부정어 필터
│   └── distributor.py      #   합의 → 에이전트 강점별 작업 매핑
│
├── context/                # 공유 두뇌
│   ├── shared.py           #   SharedContextEngine — shared.md 관리
│   ├── monitor.py          #   에이전트별 토큰 사용량 추적
│   └── rotator.py          #   컨텍스트 한계 도달 시 자동 세션 교체
│
├── completion/             # 에이전트 응답 완료 감지
│   ├── base.py             #   CompletionDetector ABC + FallbackChainDetector
│   ├── hook.py             #   Claude 정지 훅 파일 시그널
│   ├── idle.py             #   출력 변경 정지 감지기
│   └── prompt.py           #   CLI 프롬프트 재등장 감지기
│
├── tui/                    # 인터랙티브 터미널 UI
│   ├── app.py              #   TrinityTUI — Rich Live 렌더링 엔진
│   ├── session.py          #   InteractiveSession — 입력 루프 + 이벤트 구동 업데이트
│   ├── events.py           #   TUIEventBus — 스레드 안전 이벤트 브릿지
│   └── theme.py            #   에이전트별 비주얼 테마 (색상, 아이콘, 역할)
│
├── setup/                  # 첫 실행 경험
│   ├── detector.py         #   설치된 AI CLI 자동 감지
│   └── wizard.py           #   Rich 인터랙티브 설정 위자드
│
├── tmux/                   # 인터랙티브 모드 인프라
│   ├── pane.py             #   저수준 tmux pane I/O
│   ├── session.py          #   세션/pane 라이프사이클 관리
│   └── layout.py           #   TUI + 에이전트 분할 레이아웃
│
├── workspace/              # 에이전트 격리
│   ├── isolation.py        #   에이전트별 git worktree (병렬 편집)
│   └── managed_home.py     #   에이전트별 격리된 HOME 디렉토리
│
├── health/
│   └── checker.py          #   에이전트 헬스 모니터링
│
├── retry.py                #   지수 백오프 + 지터가 포함된 RetryConfig
└── error_handler.py        #   크래시 복구 및 에이전트 재시작
```

### 핵심 설계 결정

| 결정 | 이유 |
| :--- | :--- |
| **공유 마크다운 파일** | 에이전트가 `shared.md`에 읽기/쓰기 — 단순, 투명, 디버깅 가능 |
| **라운드 기반 프로토콜** | 구조화된 토론이 순환 논쟁을 방지하고 진행을 강제 |
| **이벤트 구동 TUI** | `asyncio.wait(FIRST_COMPLETED)` + `Queue`로 실시간 스트리밍 구현 |
| **키워드 합의 감지** | 빠르고 결정론적인 합의 감지 + 부정어 필터링 |
| **프로바이더 비의존 에이전트** | `AgentWrapper` ABC — 새 AI 프로바이더 추가 용이 |
| **두 실행 모드** | Print 모드 (CI/스크립트) + 인터랙티브 모드 (tmux/라이브) |

---

## 🔧 사전 요구사항

| 요구사항 | 이유 | 필수 여부 |
| :--- | :--- | :--- |
| **Python 3.10+** | 런타임 | ✅ 필수 |
| **Claude Code CLI** | 설계자 에이전트 | 선택 |
| **Codex CLI** | 구현자 에이전트 | 선택 |
| **Gemini CLI** | 검토자 에이전트 | 선택 |
| **tmux** | 인터랙티브 모드 | 선택 |

> 최소 **하나** 이상의 AI CLI가 설치되어 있어야 합니다. `trinity init` 시 가용 CLI를 자동 감지합니다.

---

## 🧪 개발

```bash
# 클론 및 설정
git clone https://github.com/hongdangmoo49/Trinity.git
cd Trinity
uv sync

# 테스트 실행 (596개 테스트)
uv run pytest tests/ -v

# 커버리지 포함 실행
uv run pytest tests/ --cov=trinity --cov-report=term-missing
```

### 배포

```bash
# pyproject.toml + src/trinity/__init__.py 버전 업
rm -rf dist/
uv build
uv publish --token <PYPI_TOKEN>
```

---

## 📊 프로젝트 통계

| 항목 | 값 |
| :--- | :--- |
| **버전** | 0.3.0 |
| **테스트** | 596개 통과 |
| **커버리지** | ~87% |
| **소스 파일** | 40+ |
| **의존성** | `click`, `rich`, `tomli` |
| **Python** | 3.10+ |

---

## 📄 라이선스

MIT License — [LICENSE](https://github.com/hongdangmoo49/Trinity/blob/main/LICENSE) 파일을 참조하세요.

---

<div align="center">

*"세 개의 머리가 하나보다 낫다."*

**Trinity** — [`GitHub`](https://github.com/hongdangmoo49/Trinity) · [`PyPI`](https://pypi.org/project/trinity-agent/) · [`Issues`](https://github.com/hongdangmoo49/Trinity/issues)

</div>
