# Phase 9: TUI/UX 대수선 (Overhaul) 설계 문서

> **상태**: 설계 완료 — 코드 수정 없음
> **날짜**: 2026-06-02
> **관련 Phase**: v0.6.0 이후, v0.7.0 마일스톤

---

## 문제 정의

v0.6.0에서 실제 사용자가 `trinity` TUI를 실행한 결과, **6가지 심각한 UX 결함**이 확인되었다.
이 결함들은 사용자가 에이전트의 의견을 읽을 수 없고, 세션이 멈추며, 기본적인 터미널 인터랙션이 깨지는 수준이다.

---

## 문제 1: 세션 멈춤 (Session Freeze)

### 현상
합의 실패/성공 후 세션이 멈춰버림. 사용자가 다음 질문을 입력할 수 없음.

### 근본 원인 분석

**`session.py:347-409` — `_run_with_live()` 흐름:**

```
Live refresh 루프:
  while thread.is_alive():
      thread.join(timeout=0.25)
      for event in bus.poll(): tui.consume_event(event)
      live.update(tui.build_layout())
```

`Live(transient=True)`로 설정되어 있어, Live 컨텍스트가 종료되면 화면이 지워진다.
하지만 **`_display_result()` (line 413-453)가 `console.print()`로 결과를 출력한 뒤,
`_run_deliberation()`이 return하고 메인 루프가 `Prompt.ask()`로 돌아와야 하는데,
여기서 멈추는 현상이 발생한다.**

실제 원인은 두 가지 가능성:
1. **백그라운드 스레드 예외**: `_run_async()`에서 `asyncio.run()`이 완료되지 않았거나, tmux 프로세스가 좀비 상태로 남아 `thread.is_alive()`가 계속 `True`를 반환
2. **`Prompt.ask()` 블로킹**: Rich의 `Prompt.ask()`는 내부적으로 `input()`을 사용하며, stdin이 tmux/파이프에서 비정상 동작할 수 있음

### 설계

1. **스레드 타임아웃 가드 추가**:
   ```python
   # _run_with_live() 내부
   max_wait = 300  # 5분 하드 리미트
   start = time.time()
   while thread.is_alive():
       if time.time() - start > max_wait:
           logger.warning("Deliberation thread timeout after %ds", max_wait)
           break
       thread.join(timeout=0.25)
       ...
   ```

2. **오류 후 상태 복구 보장**: `_run_deliberation()`의 `except` 블록에서 tmux 세션 정리 및 TUI 리셋 명시적 호출

3. **`DELIBERATION_DONE` 이벤트 활용**: 이벤트가 발생하면 즉시 Live 루프 종료 (`thread.is_alive()` 폴링에만 의존하지 않음)

### 영향 파일
- `src/trinity/tui/session.py` — `_run_with_live()`, `_run_deliberation()`

---

## 문제 2: 에이전트 출력 왜곡 (Garbled Agent Output)

### 현상
TUI에서 에이전트 의견이 CLI 스플래시 화면, 배너, 프롬프트 문자 등과 뒤섞여 알아볼 수 없는 상태로 표시됨.

예시 (실제 출력):
```
│ │ user@DESKTOP-JL8L7B 7:~/workspace/Trini ty$ claude --danger ously-skip-permissi ons
│ │ Welcome back!  │ │  ▐▛███▜▌ │ │  ▝▜█████▛▘
│ │ Tip: GPT-5.5 is now available in Codex...
```

### 근본 원인 분석

**`tmux/pane.py`의 `capture()`는 `tmux capture-pane -p`만 사용** — ANSI 코드는 제거되지만:
- Claude Code 스플래시 아트 (█████, ▐▛███▜▌)
- Codex 시작 배너 (`>_ OpenAI Codex (v0.136.0)`)
- Gemini 마이그레이션 알림
- 프롬프트 기호 (`>`, `❯`, `$`)
- CLI 팁 메시지

이 모든 것이 **응답 텍스트로 그대로 캡처**된다.

**`claude_agent.py:_extract_response()`의 한계:**
1. `self._sent_text[:50]`으로 프롬프트 경계를 찾음 — 하지만 tmux가 긴 텍스트를 줄바꿈하면 50자 매칭이 실패할 수 있음
2. 매칭 실패 시 **마지막 100줄 전체를 응답으로 간주** (fallback) — 여기에 스플래시/배너가 포함됨
3. 응답 내부에 CLI가 출력한 메타 텍스트(진행률, 팁, 모델 정보)를 걸러내는 로직이 **전혀 없음**

### 설계

#### 2A. 응답 정제 파이프라인 (`ResponseCleaner`)

```python
# src/trinity/agents/response_cleaner.py (신규)

class ResponseCleaner:
    """에이전트 raw 응답에서 실제 의견 텍스트만 추출."""
    
    # CLI별 패턴
    SPLASH_PATTERNS = [
        r'Welcome back!',
        r'▐▛███▜▌', r'▝▜█████▛▘',     # Claude 아스키 아트
        r'>_ OpenAI Codex',               # Codex 배너
        r'Gemini CLI',                     # Gemini 배너
        r'Tip:', r'Tips for',             # 팁 섹션
        r'Shell mode enabled',            # 셸 모드 알림
        r'/model to change',              # 모델 변경 안내
        r'migrate to Antigravity',         # 마이그레이션 알림
    ]
    
    PROMPT_PATTERNS = [
        r'^[>❯$]\s*$',                   # 빈 프롬프트 라인
        r'^\s*Read the shared context',   # 반복된 프롬프트 헤더
        r'^\s*User.s request:',           # 사용자 질문 반복
    ]
    
    def clean(self, raw: str) -> str:
        lines = raw.split('\n')
        # 1. 스플래시/배너 라인 제거
        # 2. 프롬프트 라인 제거
        # 3. 빈 라인 정리
        # 4. 실제 응답 시작점 탐지 (의미있는 텍스트가 시작되는 줄)
        return cleaned_text
```

#### 2B. `_extract_response()` 개선

- 현재의 프롬프트 경계 매칭을 더 견고하게 개선 (줄바꿈/워래핑 처리)
- `ResponseCleaner`를 파이프라인 마지막에 적용
- 스플래시 비율이 50% 이상이면 경고 로그 + 빈 응답 처리

### 영향 파일
- `src/trinity/agents/response_cleaner.py` — **신규**
- `src/trinity/agents/claude_agent.py` — `_extract_response()`
- `src/trinity/agents/codex_agent.py` — `_extract_response()` (있는 경우)
- `src/trinity/agents/gemini_agent.py` — `_extract_response()` (있는 경우)

---

## 문제 3: 언어 설정 미반영 (Language Not Respected)

### 현상
`trinity init`에서 한국어를 선택했지만, 에이전트의 실제 응답과 프로토콜 프롬프트가 영어로만 출력됨.

### 근본 원인 분석

**현재 언어 흐름의 한계:**

```
init 시: lang="ko" → ROLE_PROMPTS["ko"]["claude"] = "당신은 아키텍트입니다..."
         ↓
         AgentSpec.role_prompt에 한글 역할 프롬프트 저장
         ↓
         TOML에 저장 (lang 필드 자체는 저장 안 됨)
         ↓
실제 실행 시:
         프로토콜: _build_round_prompt() → 항상 영어
                  "Share your initial opinion. Be specific and concise."
                  "For each other agent's opinion above, state whether you AGREE or DISAGREE"
         ↓
         에이전트는 한글 역할 프롬프트를 받지만, 턴 프롬프트는 영어
         → 영어로 응답하는 것이 자연스러운 결과
```

**핵심 문제:**
1. `DeliberationProtocol`에 `lang` 매개변수가 없음
2. `_build_round_prompt()`의 모든 템플릿이 하드코딩 영어
3. 합의 결과 (`ConsensusResult.summary`), 작업 분배 설명도 영어
4. `TrinityConfig`에 `lang` 필드가 없어 런타임에 언어를 알 수 없음

### 설계

#### 3A. `TrinityConfig.lang` 필드 추가

```python
@dataclass
class TrinityConfig:
    ...
    lang: str = "en"  # i18n 언어 코드
```

- `_from_dict()`에서 읽기, `save()`에서 쓰기
- 기존 TOML에 `lang` 키가 없으면 `"en"`으로 기본값

#### 3B. `DeliberationProtocol`에 언어 전달

```python
class DeliberationProtocol:
    def __init__(self, ..., lang: str = "en"):
        self.lang = lang
```

#### 3C. 라운드 프롬프트 현지화

```python
# i18n.py에 추가
ROUND_PROMPTS = {
    "en": {
        "round1": "Read the shared context below for background.\n"
                  "User's request: {prompt}\n"
                  "Share your initial opinion...",
        "round2_plus": "For each other agent's opinion above...",
        "caveman_reinforcement": { ... }
    },
    "ko": {
        "round1": "아래 공유 컨텍스트를 배경으로 읽으세요.\n"
                  "사용자 요청: {prompt}\n"
                  "초기 의견을 제시해주세요...",
        "round2_plus": "다른 에이전트의 의견에 대해 동의하는지...",
        "caveman_reinforcement": { ... }  # 영어 유지 (토큰 절감)
    }
}
```

#### 3D. TUI 라벨 현지화 (이미 부분 구현됨)

- 합의 라벨: `"✅ 합의 도달!"` / `"❌ 합의 실패"` — 이미 한국어
- 결과 패널: `"소요시간"`, `"토큰"`, `"라운드"` — 이미 한국어
- **추가 필요**: 라운드 프롬프트만 i18n 적용하면 에이전트 응답 언어가 자연스럽게 일치됨

### 영향 파일
- `src/trinity/config.py` — `lang` 필드 추가
- `src/trinity/i18n.py` — `ROUND_PROMPTS` 추가
- `src/trinity/deliberation/protocol.py` — `lang` 매개변수, `_build_round_prompt()` 현지화
- `src/trinity/orchestrator.py` — `config.lang` → `DeliberationProtocol(lang=)` 전달

---

## 문제 4: 응답 글자수 제한 상향 (Response Preview Truncation)

### 현상
에이전트의 의견이 40~500자로 심하게 잘려서 표시됨. 실제 응답은 수천 자인데 TUI에서는 거의 볼 수 없음.

### 현재 제한값

| 위치 | 제한 | 용도 |
|------|------|------|
| `app.py:150` | **80자** | `AGENT_RESPONDED` 이벤트 시 첫 미리보기 |
| `app.py:255` | **40자** | 에이전트 상태 테이블 `Response Preview` 컬럼 |
| `app.py:333` | **500자** | 숙의 패널 내 마크다운 렌더링 |

### 설계

TUI는 터미널 너비에 맞춰 동적으로 계산:

```python
import shutil

TERMINAL_WIDTH = shutil.get_terminal_size().columns  # 기본 80

# 제한값을 터미널 너비의 비율로 설정
PREVIEW_CHARS = max(200, TERMINAL_WIDTH * 3)   # 상태 테이블용 (기존 40→약 240)
OPINION_CHARS = max(2000, TERMINAL_WIDTH * 10)  # 숙의 패널용 (기존 500→약 800)
```

**추가 개선 — 접기/펼치기:**
- 기본적으로 첫 3줄만 표시
- `[더보기]` 표시 → 사용자가 클릭/엔터 시 전체 내용 출력
- `/history <N>` 명령어로 특정 라운드의 전체 응답 조회 가능

### 영향 파일
- `src/trinity/tui/app.py` — `consume_event()`, `build_deliberation_panel()`, `build_agent_panel()`

---

## 문제 5: TUI 테이블 단순화 (Simplify TUI Tables)

### 현상
에이전트 상태 테이블과 작업 분배 테이블이 터미널에서 너무 복잡하게 깨져서 표시됨.

```
┏━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Agent     ┃ Task                                            ┃ Priority ┃
┡━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ 🏗️ claude │  As 당신은 아키텍트입니다, execute on the...    │        0 │
```

**문제점:**
- 터미널 너비를 초과하는 테이블 → Rich가 자동 줄바꿈 → 가독성 파괴
- `Task` 컬럼에 "As 당신은 아키텍트입니다, execute on the agreed conclusion. Consensus: Consensus..." 같은 기계적 텍스트
- `Response Preview` 컬럼이 실제 응답이 아닌 캡처된 raw 터미널 출력을 보여줌

### 설계

#### 5A. 에이전트 상태 — 파일럿 뷰 (Pilot View)

기존 복잡한 테이블을 **간결한 파일럿 뷰**로 교체:

```
┌─────────────────────────────────────────────────┐
│ 🧠 Trinity v0.6.0  —  Three minds, one context  │
│                                                 │
│   🏗️ claude ✅    ⚙️ codex ✅    🔍 gemini ✅   │
│                                                 │
│ 📡 Session: trinity  ⏱ 1m 21s                   │
│   🦴 CAVEMAN:FULL                               │
│                                                 │
╰─────────────────────────────────────────────────╯
```

이것만으로 충분. 상세 상태는 `/status` 명령어로만 표시.

#### 5B. 숙의 패널 — 카드 레이아웃

에이전트 의견을 테이블이 아닌 **카드 스택**으로 표시:

```
── Round 1 ──────────────────────────────────────────

  ✅ claude (Architect)
  ┌───────────────────────────────────────────────┐
  │ 이더리움 고래 추적을 위한 아키텍처 설계:      │
  │ 1. Etherscan WebSocket API를 활용한 실시간... │
  │ 2. 필터링 기준: 거래액 > $100K...            │
  │ ...                                           │
  └───────────────────────────────────────────────┘

  ✅ codex (Implementer)
  ┌───────────────────────────────────────────────┐
  │ Python 기반 고래 추적 봇 구현 방안:           │
  │ web3.py + asyncio를 사용한...                 │
  └───────────────────────────────────────────────┘

  ❌ 합의 실패  0/3 동의 (0%)
```

#### 5C. 결과 패널 — 요약 + 작업 리스트

```
── Result ──────────────────────────────────────────

  ✅ 합의 도달 (Round 4)  2/3 동의

  📋 합의 요약:
  ┌───────────────────────────────────────────────┐
  │ Etherscan API + WebSocket 기반 실시간 추적... │
  └───────────────────────────────────────────────┘

  🎯 작업 분배:
    🏗️ claude: 아키텍처 설계 및 API 스펙 정의
    ⚙️ codex: Python 봇 구현
    🔍 gemini: 코드 리뷰 및 최적화

  소요시간: 73.8s | 토큰: 12,450 | 라운드: 4
```

**테이블 대신 간단한 리스트** 사용. `Tree` 위젯은 계층적 데이터에만 적합하고, 평면적인 작업 분배에는 과함.

### 영향 파일
- `src/trinity/tui/app.py` — `build_agent_panel()`, `build_deliberation_panel()`, `build_result_panel()`
- `src/trinity/tui/session.py` — `_display_result()`

---

## 문제 6: 입력 UX 개선 (Input UX — Arrow Key Handling)

### 현상
```
💬 trinity>: ^[[A^[[B^[[D^[[D^C
Use /quit to exit.
```
방향키 입력이 raw 이스케이프 시퀀스로 출력됨. 위아래 히스토리, 좌우 커서 이동 불가.

### 근본 원인

**`session.py:96-98` — `Prompt.ask()` 사용:**

```python
def _get_input(self) -> str:
    return Prompt.ask("\n[bold green]💬 trinity>[/bold green]", console=self.console)
```

`rich.prompt.Prompt.ask()`는 내부적으로 Python의 `input()`을 호출함.
`input()`은 **라인 편집 기능이 전혀 없음**:
- 방향키 → 이스케이프 시퀀스 그대로 출력
- 명령어 히스토리 없음
- 자동완성 없음
- 커서 이동 불가

### 설계

#### 6A. `prompt_toolkit` 도입

`prompt_toolkit`은 Python 터미널 입력의 사실상 표준:
- 방향키 히스토리 (위/아래)
- 커서 이동 (좌/우, Home/End)
- Tab 자동완성
- Emacs/Vi 모드
- 색상 프롬프트
- 멀티라인 입력

```toml
# pyproject.toml
dependencies = [
    "click>=8.1",
    "rich>=13.0",
    "prompt_toolkit>=3.0",
    "tomli>=2.0; python_version < '3.11'",
]
```

#### 6B. `TrinityPromptSession` 구현

```python
# src/trinity/tui/prompt.py (신규)

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.lexers import Lexer

class TrinityPromptSession:
    """prompt_toolkit 기반 입력 세션."""
    
    def __init__(self, config: TrinityConfig):
        history_path = config.effective_state_dir / "history" / "input_history"
        self.session = PromptSession(
            history=FileHistory(str(history_path)),
            auto_suggest=AutoSuggestFromHistory(),
            multiline=False,
            prompt_continuation="... ",
        )
    
    def get_input(self) -> str:
        """사용자 입력 받기. 방향키, 히스토리, 자동완성 지원."""
        try:
            return self.session.prompt(
                [("class:prompt", "💬 trinity> ")],
                style=Style.from_dict({"prompt": "bold green"}),
            )
        except KeyboardInterrupt:
            raise
        except EOFError:
            raise
```

#### 6C. 자동완성

```python
from prompt_toolkit.completion import WordCompleter

COMMANDS = WordCompleter([
    "/status", "/context", "/rounds", "/agent",
    "/history", "/save", "/caveman", "/help", "/quit",
])
```

Tab 키로 `/` 명령어 자동완성.

### 영향 파일
- `pyproject.toml` — `prompt_toolkit` 의존성 추가
- `src/trinity/tui/prompt.py` — **신규**
- `src/trinity/tui/session.py` — `_get_input()` 교체, 의존성 변경

---

## 구현 우선순위

| 순서 | 문제 | 난이도 | 영향 | 의존성 |
|------|------|--------|------|--------|
| **1** | P2: 출력 왜곡 | 중 | **치명적** — 응답 자체가 안 보임 | 없음 |
| **2** | P6: 입력 UX | 중 | **높음** — 기본 인터랙션 | prompt_toolkit |
| **3** | P1: 세션 멈춤 | 낮 | **높음** — UX 차단 | 없음 |
| **4** | P3: 언어 미반영 | 중 | 중 — i18n 완성도 | config.lang |
| **5** | P5: 테이블 단순화 | 낮 | 중 — 가독성 | P2 선행 |
| **6** | P4: 글자수 상향 | 낮 | 낮 — P2 해결 시 자연 해결 | P2 선행 |

**P2(출력 왜곡)가 모든 것의 선행 조건** — 응답이 제대로 캡처되지 않으면 글자수 상향도, 테이블 개선도 의미가 없다.

---

## 파일 변경 요약

| 파일 | 변경 유형 | 문제 |
|------|-----------|------|
| `src/trinity/agents/response_cleaner.py` | **신규** | P2 |
| `src/trinity/tui/prompt.py` | **신규** | P6 |
| `src/trinity/agents/claude_agent.py` | 수정 | P2 |
| `src/trinity/agents/codex_agent.py` | 수정 | P2 |
| `src/trinity/agents/gemini_agent.py` | 수정 | P2 |
| `src/trinity/tui/app.py` | 수정 | P4, P5 |
| `src/trinity/tui/session.py` | 수정 | P1, P6 |
| `src/trinity/config.py` | 수정 | P3 |
| `src/trinity/i18n.py` | 수정 | P3 |
| `src/trinity/deliberation/protocol.py` | 수정 | P3 |
| `src/trinity/orchestrator.py` | 수정 | P3 |
| `pyproject.toml` | 수정 | P6 |
| `tests/test_response_cleaner.py` | **신규** | P2 |
| `tests/test_tui_prompt.py` | **신규** | P6 |

---

## 위험 및 고려사항

1. **prompt_toolkit + Rich Live 충돌**: `prompt_toolkit`은 자체 터미널 제어를 하므로 Rich Live와 충돌 가능. 해결: Live가 활성화된 동안은 입력 비활성화, Live 종료 후 입력 활성화
2. **응답 정제 과청소**: 너무 공격적인 패턴 매칭이 실제 응답을 삭제할 위험. 해결: 화이트리스트가 아닌 블랙리스트 방식 (알려진 CLI 패턴만 제거)
3. **prompt_toolkit 번들 크기**: ~2MB 추가. Trinity는 CLI 도구이므로 수용 가능
4. **기존 TOML 호환성**: `lang` 필드가 없는 기존 설정 파일은 기본값 `"en"`으로 처리 — 마이그레이션 불필요
