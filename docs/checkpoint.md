# Trinity Checkpoint — 2026-06-01

> Phase 1 완료 시점의 프로젝트 상태와 앞으로의 로드맵.

---

## Phase 1: 최소 작동 프로토타입 — ✅ 완료

### 구현된 것

| 컴포넌트 | 파일 | 상태 | 설명 |
|----------|------|------|------|
| **프로젝트 구조** | `pyproject.toml` | ✅ | uv 기반, click + rich 의존성 |
| **데이터 모델** | `src/trinity/models.py` | ✅ | AgentSpec, DeliberationMessage, ContextUsage, ConsensusResult, TaskAssignment, AgentHealth |
| **설정 로더** | `src/trinity/config.py` | ✅ | TOML 기반 TrinityConfig, load/save/default, 에이전트 필터링 |
| **tmux 저수준** | `src/trinity/tmux/pane.py` | ✅ | TmuxPane: send_keys, send_text_heredoc, capture, is_alive, kill |
| **tmux 세션** | `src/trinity/tmux/session.py` | ✅ | TmuxSessionManager: 세션 생성, pane 분할, 레이아웃 |
| **에이전트 추상** | `src/trinity/agents/base.py` | ✅ | AgentWrapper ABC: start, send_and_wait, get_context_usage, is_alive |
| **Claude 에이전트** | `src/trinity/agents/claude_agent.py` | ✅ | PrintModeClaudeAgent: `claude -p --output-format json` 서브프로세스 |
| **공유 컨텍스트** | `src/trinity/context/shared.py` | ✅ | SharedContextEngine: shared.md 섹션 CRUD, keep_sections, 세션 교체 컨텍스트 |
| **합의 판정** | `src/trinity/deliberation/consensus.py` | ✅ | ConsensusEngine: 키워드 기반 (한/영), 임계값 설정 |
| **작업 분담** | `src/trinity/deliberation/distributor.py` | ✅ | TaskDistributor: 에이전트 강점 매핑, 우선순위 부여 |
| **토론 프로토콜** | `src/trinity/deliberation/protocol.py` | ✅ | DeliberationProtocol: 라운드 루프, 병렬 수집, 합의 판정 |
| **오케스트레이터** | `src/trinity/orchestrator.py` | ✅ | TrinityOrchestrator: 전체 컴포넌트 연결, lazy init |
| **CLI** | `src/trinity/cli.py` | ✅ | Click 기반: init, ask, status, context |
| **템플릿** | `templates/trinity.config.example` | ✅ | 기본 3에이전트 설정 예시 |
| **테스트** | `tests/` (5개 파일) | ✅ | 50개 테스트 전부 통과 |

### 작동 방식

```
trinity ask "질문"
  → PrintModeClaudeAgent가 claude -p --output-format json 서브프로세스 실행
  → JSON에서 응답 텍스트 + 토큰 사용량 추출
  → SharedContextEngine이 shared.md에 섹션 단위로 기록
  → ConsensusEngine이 키워드로 합의 판정
  → TaskDistributor가 에이전트 강점에 따라 분담
  → Rich로 결과 출력
```

### Phase 1의 핵심 단순화

- **`claude -p` 서브프로세스 방식**: tmux 인터랙티브 모드가 아닌 서브프로세스 호출로 완료 감지·토큰 카운트를 간단히 해결
- **단일 Provider**: Claude Code만 실제 연동, Codex/Gemini는 폴백으로 Claude print mode 사용
- **세션 교체 미구현**: Context 모니터링은 모델만 있고 자동 교체 로직은 Phase 3

### 검증 완료

- [x] `uv sync` 설치 성공
- [x] `trinity --version` → `trinity, version 0.1.0`
- [x] `trinity init` → `.trinity/` 디렉토리 + 설정 파일 생성
- [x] `trinity status` → 에이전트 상태 테이블 출력
- [x] `pytest tests/ -v` → 50 passed
- [x] GitHub push 완료

---

## Phase 2: tmux 인터랙티브 모드 — 🔲 예정

### 목표
에이전트를 tmux pane에서 지속 실행, 다중 라운드 토론을 시각적으로 확인.

### 구현해야 할 것

| 작업 | 파일 | 상세 |
|------|------|------|
| **InteractiveClaudeAgent** | `agents/claude_agent.py` | tmux pane에서 `claude` 실행, send-keys로 프롬프트 주입, capture-pane으로 출력 읽기 |
| **완료 감지 — IdleDetector** | `completion/idle_detector.py` | capture-pane 출력 변화 없으면 N초 후 완료로 판정 (Gemini용) |
| **완료 감지 — PromptReturnDetector** | `completion/prompt_detector.py` | Claude의 `>` 또는 `$` 프롬프트 재등장 감지 |
| **완료 감지 — HookDetector** | `completion/hook_detector.py` | Claude Stop-hook이 파일에 쓰는 완료 신호 watch |
| **다중 라운드 시각화** | `deliberation/protocol.py` 개선 | 각 라운드 결과를 tmux pane 타이틀에 반영, 진행 상태 표시 |
| **에이전트 시작 시 역할 주입** | `agents/claude_agent.py` | `--append-system-prompt` 또는 첫 send_keys로 role_prompt 주입 |

### 난관 예상

| 문제 | 위험도 | 대응 |
|------|--------|------|
| Claude CLI 프롬프트 패턴 변경 | 중간 | 정규식을 넓게 잡고 fallback 체인 구성 (Hook → PromptReturn → Idle) |
| send-keys 특수문자 이스케이프 | 높음 | heredoc + temp file 방식으로 우회 (pane.py에 이미 구현됨) |
| Gemini 완료 감지 불안정 | 높음 | idle 타임아웃을 20초로 길게, 하드 타임아웃 120초 |
| tmux 레이아웃 깨짐 | 중간 | `tmux -f /dev/null` + `select-layout even-horizontal` (session.py에 이미 반영) |

### 마일스톤

```
trinity ask "인증 시스템 설계해줘"
  → tmux 3분할 화면에 claude/codex/gemini가 각각 실행
  → 3라운드 토론이 pane에서 실시간으로 보임
  → 합의 도달 시 분담 결과가 각 pane에 전달
```

---

## Phase 3: Context 모니터링 + 자동 세션 교체 — 🔲 예정

### 목표
에이전트의 context 사용량이 60%에 도달하면 자동으로 세션을 교체, 이전 작업 요약을 새 세션에 주입.

### 구현해야 할 것

| 작업 | 파일 | 상세 |
|------|------|------|
| **ContextMonitor** | `context/monitor.py` | Provider별 토큰 카운트 파싱, 60% 임계 체크 |
| **SessionRotator** | `context/rotator.py` | 요약 요청 → shared.md 업데이트 → 세션 종료 → 새 세션 시작 (요약+shared.md 주입) |
| **토큰 카운트 — Claude** | `agents/claude_agent.py` 개선 | Stop-hook 출력의 usage 필드, 또는 `--output-format json`에서 추출 |
| **토큰 카운트 — Codex** | `agents/codex_agent.py` | 세션 JSON 파일의 `usage.total_tokens` 폴링 |
| **토큰 카운트 — Gemini** | `agents/gemini_agent.py` | CLI 출력에서 `Token count:` 정규식 (불안정, fallback 필요) |
| **keep_sections 메커니즘 검증** | `context/shared.py` 개선 | 세션 교체 시 pinned 섹션이 새 세션에 정확히 전달되는지 |
| **다른 에이전트에게 세션 교체 알림** | `deliberation/protocol.py` 개선 | "[claude 세션이 교체되었습니다]" 브로드캐스트 |

### 핵심 플로우

```
ContextMonitor: "Claude context 62%!"
  → SessionRotator.rotate("claude")
    1. claude에게 "작업 요약해줘" 요청
    2. shared.md에 세션 히스토로그 추가
    3. claude 세션 종료
    4. shared.md(keep_sections) + 요약을 첫 프롬프트로 새 세션 시작
    5. 다른 에이전트에게 알림
```

### 마일스톤

```
긴 토론 세션 (10+ 라운드) 실행 중
  → Claude context 60% 도달
  → 자동으로 "작업 요약 중..." 출력
  → 새 Claude 세션이 이전 맥락을 이어서 작업 재개
  → 다른 에이전트는 중단 없이 계속
```

---

## Phase 4: 다중 Provider + 헬스체크 — 🔲 예정

### 목표
Codex, Gemini CLI를 네이티브로 지원하고 에이전트 간 헬스체크 구현.

### 구현해야 할 것

| 작업 | 파일 | 상세 |
|------|------|------|
| **CodexAgent** | `agents/codex_agent.py` | Codex CLI 제어: 세션 파일 탐색, 폴링, managed home |
| **GeminiAgent** | `agents/gemini_agent.py` | Gemini CLI 제어: idle 타임아웃, 마커 주입 |
| **AgentFactory** | `agents/factory.py` | config → provider별 에이전트 인스턴스 생성 (orchestrator에서 분리) |
| **HealthChecker** | `health/checker.py` | pane 생존, context %, 진행 상태 주기적 체크 |
| **Provider별 완료 감지 분리** | `completion/` 하위 | Claude/Codex/Gemini 각각 전용 detector |
| **Workspace 격리** | 새 모듈 | git-worktree 생성/관리 (.trinity/workspace/<agent>/) |
| **Managed Home** | 새 모듈 | 에이전트별 격리 홈 (.trinity/agents/<name>/provider-state/) |

### Provider별 구현 난이도

| Provider | 완료 감지 | 토큰 카운트 | 격리 홈 | 전체 난이도 |
|----------|----------|------------|---------|------------|
| **Claude Code** | ★★☆ (hook/prompt) | ★☆☆ (JSON) | ★★☆ | 중간 |
| **Codex** | ★★☆ (세션 파일) | ★☆☆ (JSON) | ★★★ (config.toml) | 중간~높음 |
| **Gemini CLI** | ★★★ (불안정) | ★★★ (정규식) | ★★☆ | 높음 |

### 마일스톤

```
trinity ask "인증 시스템 설계해줘"
  → Claude(아키텍트) + Codex(구현자) + Gemini(리뷰어)가 동시에 토론
  → 합의 후 Codex는 격리 worktree에서 구현
  → 에이전트 간 헬스체크로 진행 상태 모니터링
  → context limit 도달 시 자동 세션 교체
```

---

## Phase 5: 프로덕션 폴리싱 — 🔲 예정

### 구현해야 할 것

| 작업 | 상세 |
|------|------|
| `trinity attach` | tmux 세션에 attach |
| `trinity logs --follow` | 오케스트레이터 로그 실시간 출력 |
| `trinity config --show <key>` | 설정 값 확인 |
| `trinity reset --keep-context` | 세션 초기화 (shared.md 보존 옵션) |
| 재시도 로직 | RetryConfig: CLI 종료 코드 + 출력 패턴 기반, 지수 백오프 |
| 에러 핸들링 | Provider 크래시 → 자동 respawn, 세션 복구 |
| 로깅 개선 | 파일 로깅 + Rich 콘솔 포맷팅 |
| `trinity status --watch` | 실시간 상태 대시보드 (top 명령어 스타일) |

---

## 아키텍처 부채 (현재 알려진 것)

| 항목 | 설명 | 해결 시점 |
|------|------|-----------|
| **단일 Provider 의존** | Codex/Gemini이 Claude print mode로 폴백 | Phase 4 |
| **동기적 토론** | 라운드가 끝나야 다음 라운드 진행 | Phase 4+ (비동기 메시지 패싱) |
| **키워드 기반 합의** | "I disagree"에도 "agree"가 매칭됨 (테스트에서 확인) | Phase 3 (LLM 판정 또는 정형 출력) |
| **공유 파일 쓰기 동시성** | 두 에이전트가 동시에 shared.md 쓰면 충돌 가능 | Phase 3 (파일 락 또는 직렬화) |
| **세션 교체 미구현** | ContextUsage 모델만 있고 자동 교체 없음 | Phase 3 |
| **tmux 미사용** | Phase 1은 서브프로세스만, tmux 레이어가 연결 안 됨 | Phase 2 |

---

## 참고

- **레포**: https://github.com/hongdangmoo49/Trinity
- **참고 아키텍처**: `docs/reference-architecture.md`
- **구현 계획**: `/home/user/.claude/plans/resilient-kindling-tome.md`
- **마지막 커밋**: `eefb8cb` — feat: implement Trinity v0.1.0 — Phase 1 core

*작성일: 2026-06-01*
