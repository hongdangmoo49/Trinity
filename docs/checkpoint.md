# Trinity Checkpoint — 2026-06-01

> Phase 1 완료 시점의 프로젝트 상태와 앞으로의 로드맵.
> 각 구현 Phase 다음에 테스트 Phase(Phase N-T)를 배치하여 테스트 부채 누적을 방지.
> 공유 파일 동시성 문제는 오케스트레이터 중앙 집중 쓰기(방안 1)로 설계상 회피.

---

## Current Baseline — v0.10.3

작성일: 2026-06-06

현재 브랜치 기준 최신 패키지/CLI 버전은 `0.10.3`다. v0.7.0 workflow engine
재설계 이후 target workspace boundary, Gemini 제거 및 Antigravity 전환,
cross-platform 안정화, Textual Workbench 기본 UI, Textual execution wiring까지
반영되어 있다.

### 현재 동작 모델

- 기본 대화형 실행은 Textual Workbench다. `trinity --plain` 또는 `TRINITY_TUI=plain`은
  기존 Rich/prompt_toolkit TUI fallback을 사용한다.
- 기본 provider transport는 one-shot CLI invocation이다. legacy tmux transport는
  `transport_mode = "tmux"` 또는 legacy bootstrap/debug 용도로 유지된다.
- planning 단계는 `WorkflowEngine`과 `TrinityOrchestrator.ask()`가 수행하며,
  provider readiness, 라운드 기반 deliberation, central synthesis, open question,
  blueprint 생성을 처리한다.
- execution 단계는 blueprint가 준비된 뒤 target workspace preflight를 통과해야 시작된다.
  provider workspace-write는 Trinity control repo 밖의 명시적 target workspace로 제한된다.
- Textual Workbench는 `TextualWorkflowController`를 통해 기존 workflow/orchestrator를
  background thread에서 실행하고, persisted workflow state와 runtime event를 snapshot으로
  화면에 투영한다.

### 최신 운영 문서

- [v0.10.3 Workflow and Runtime Guide](workflow-v0.10.2-guide.md)
- [Slash Command Reference](slash-command-reference.md)
- [Trinity Slash Command Routing Design](plans/2026-06-06-trinity-slash-command-routing-design.md)
- [Provider CLI Slash Command Backlog](plans/2026-06-06-provider-cli-slash-command-backlog.md)
- [Slash Command Routing Implementation](test-results/2026-06-06-slash-command-routing-implementation.md)
- [Slash Command Analysis Documentation](test-results/2026-06-06-slash-command-analysis.md)
- [WP Graph Synthesis Hardening Plan](plans/2026-06-06-wp-graph-synthesis.md)
- [WP Graph Synthesis Hardening Result](test-results/2026-06-06-wp-graph-synthesis.md)
- [Textual Workbench Execution Branch Report](test-results/2026-06-05-textual-workbench-execution-branch-report.md)
- [Execution Matrix Hardening](test-results/2026-06-05-execution-matrix-hardening.md)
- [Execution Timeline Logging](test-results/2026-06-06-execution-timeline-logging.md)
- [Follow-up Target Workspace Reuse](test-results/2026-06-06-followup-target-workspace-reuse.md)
- [Nexus Scrollable History](test-results/2026-06-06-nexus-scrollable-history.md)
- [Workspace Picker Latency Follow-up](test-results/2026-06-06-workspace-picker-latency.md)
- [Textual Question ID Hardening](test-results/2026-06-06-textual-question-id-hardening.md)
- [Execution Failure Hardening](test-results/2026-06-06-execution-failure-hardening.md)
- [Textual Workbench UI Screen Report](test-results/2026-06-05-textual-workbench-ui-screen-report.md)
- [Cross-platform Stability Implementation](test-results/2026-06-05-cross-platform-stability-implementation.md)
- [Target Workspace Boundary result](test-results/2026-06-05-target-workspace-boundary.md)

### 검증 기준선

- 패키지/CLI 버전: `0.10.3`
- WSL 최신 기록: `/home/zaemi/.local/bin/uv run trinity --version` -> `trinity, version 0.10.3`
- WSL 최신 전체 회귀 기록: `/home/zaemi/.local/bin/uv run pytest -q` -> `1216 passed, 1 warning in 58.14s`
- 남은 경고: 기존 계열의 `AsyncMock` runtime warning이며 slash command 보강에서 새로 도입된 실패는 아님

---

## v0.7.0 Workflow Engine Redesign — 이력 기록

작성일: 2026-06-03

> 이 섹션은 v0.7.0 재설계 당시의 구현 기준선과 후속 smoke 이력을 보존한다.
> 현재 릴리스 기준선은 위의 `Current Baseline — v0.10.3` 섹션을 우선한다.

### 구현된 기준선

- Provider readiness/auth gating
- Interactive response contract와 response artifact 저장
- Workflow state machine과 user decision loop
- Structured deliberation/blueprint consensus
- Typed Blueprint session state와 WorkflowPersistence 컴포넌트
- Blueprint decomposition과 work package 생성
- Execution protocol MVP, dependency-level 병렬 dispatch, `Task Results` 기록
- Subagent delegation reporting과 `Subtasks` 기록
- Shared ledger renderer, LifecycleGuard MVP, peer review planning foundation
- 명시적 `/answer` user decision UX, `/questions --select` 방향키 옵션 선택
- `/questions --select --all` decision wizard
- 한국어/번호형 open question parser 보강

- Model-backed central synthesis with heuristic fallback, fixed provider priority, and fast model defaults
- Blueprint-ready 실행 의도 라우팅, deliverable-first work package 분해,
  provider load-balanced assignment, 병렬 그룹 preview
- Target workspace boundary: 구현 실행 전에 사용자 프로젝트 경로를 명시하고,
  provider workspace-write를 control repo 밖으로 제한

### 운영 문서

- [v0.7.0 Workflow Guide](workflow-v0.7.0-guide.md)
- [v0.7.0 후속 구현 후보](plans/2026-06-04-v0.7.0-follow-up-implementation-candidates.md)
- [Model-backed Central Synthesis implementation result](test-results/2026-06-04-model-backed-synthesis.md)
- [Blueprint Parallel Implementation result](test-results/2026-06-04-blueprint-parallel-implementation.md)
- [Target Workspace Boundary result](test-results/2026-06-05-target-workspace-boundary.md)
- [Provider Readiness Troubleshooting](troubleshooting-provider-readiness.md)
- [v0.7.0 Workflow Engine 테스트 결과](test-results/v0.7.0-workflow-engine.md)
- [v0.7.0 WSL/tmux Smoke Test Checklist](test-results/v070-smoke-checklist.md)

### 검증 기준선

- 당시 패키지/CLI 버전: `0.9.1`
- `uv run pytest -q` -> 1012 passed, 1 warning
- 변경 파일 대상 ruff check 통과
- 실제 WSL/tmux/provider smoke는 릴리스 전 별도 수행 필요

### Post-merge smoke follow-ups

- [x] `needs_user_decision` 상태의 일반 텍스트 FIFO 자동 기록을 제거했다.
  사용자는 `/answer <question-id|index|next> <answer>`로 대상 질문을 명시한다.
- [x] `/questions`를 실행 가능한 답변 안내 panel로 바꾸고, `/questions --select`로
  첫 pending question의 options를 방향키로 선택할 수 있게 했다.
- [x] `/questions --select --all`은 pending question을 순서대로 처리하며,
  options가 없는 질문은 자유 텍스트 답변을 받는다.
- [x] 잘못 기록한 decision은 `/answer --replace <question-id|decision-id> <answer>`로 정정한다.
- [x] 한국어 `질문/옵션/추천/이유` 필드와 빈 `Options:` 뒤 번호형 선택지를
  structured open question parser가 options/recommended/rationale로 보존한다.
- [x] WSL/tmux smoke 중 Codex pane의 과거 `model: loading` scrollback이 현재 ready prompt보다
  먼저 판정되어 continuation deliberation을 차단하는 false positive가 확인됐다.
  readiness 판정은 현재 prompt readiness를 stale loading/auth/banner scrollback보다 우선하도록 수정했다.
- [x] 후속 구현 후보를 별도 문서로 정리했다.
  우선순위는 실제 WSL/tmux smoke, peer review execution, lifecycle rotation 보강,
  non-blocking question 정책, workflow repair/reset UX 순서다.

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
| **테스트** | `tests/` (5개 파일) | ✅ | models, config, consensus, distributor, shared_context |

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
- **세션 교체 미구현**: Context 모니터링은 모델만 있고 자동 교체 로직은 ~~Phase 5~~ Phase 3에서 구현 완료
- **오케스트레이터 중앙 집중 쓰기**: shared.md의 유일한 작성자는 Orchestrator. 에이전트는 읽기만. 동시성 문제 원천 차단.

### 검증 완료

- [x] `uv sync` 설치 성공
- [x] `trinity --version` → `trinity, version 0.1.0`
- [x] `trinity init` → `.trinity/` 디렉토리 + 설정 파일 생성
- [x] `trinity status` → 에이전트 상태 테이블 출력
- [x] `pytest tests/ -v` → 50 passed
- [x] GitHub push 완료

---

## Phase 1-T: Phase 1 누락 테스트 보충 — ✅ 완료

### 목표
Phase 1에서 테스트가 없는 모듈에 대한 테스트를 작성하여 기존 50개 테스트의 커버리지 갭을 메운다.

### 구현해야 할 것

| 작업 | 파일 | 상세 |
|------|------|------|
| **Orchestrator 단위 테스트** | `tests/test_orchestrator.py` | lazy init, 에이전트 생성, Provider별 팩토리 분기, ask() 라이프사이클 (에이전트 mock), get_status() |
| **Protocol 단위 테스트** | `tests/test_protocol.py` | 라운드 루프 (합의 도달 시 조기 종료), 최대 라운드 시 강제 결론, 에이전트 예외 처리, _build_round_prompt (Round 1 vs N) |
| **CLI 통합 테스트** | `tests/test_cli.py` | `init` 명령어 (디렉토리 생성, .gitignore 갱신), `status` 명령어, `context` 명령어, `ask` 명령어 (에이전트 mock), `--max-rounds` / `--agents` 옵션 |
| **TmuxPane 단위 테스트** | `tests/test_tmux_pane.py` | send_text, capture, is_alive, kill (subprocess mock) |
| **TmuxSessionManager 단위 테스트** | `tests/test_tmux_session.py` | 세션 생성, pane 분할, 레이아웃 적용, destroy (subprocess mock) |
| **Claude Agent 단위 테스트** | `tests/test_claude_agent.py` | start, send_and_wait (subprocess mock), _parse_response, _build_prompt, 타임아웃 처리 |
| **커버리지 기준선 설정** | `pyproject.toml` | pytest-cov 추가, 최소 커버리지 80% 목표 |

### 테스트 전략

```
에이전트 테스트:
  - subprocess.run을 mock하여 claude CLI 없이 테스트
  - 정상 JSON 응답, 에러 응답, 타임아웃 케이스

프로토콜 테스트:
  - 에이전트를 Mock(AgentWrapper)으로 대체
  - ConsensusEngine을 제어하여 합의/비합의 시나리오 테스트

CLI 테스트:
  - Click의 CliRunner.invoke() 사용
  - 파일 시스템은 tmp_path fixture 사용
```

### 검증 완료

- [x] `pytest tests/ -v` → **134 passed** (기존 50개 → 84개 추가)
- [x] `pytest tests/ --cov=trinity` → **94% 커버리지** (목표 80% 초과 달성)
- [x] 모든 `src/trinity/` 모듈이 최소 1개 테스트 파일로 커버됨
- [x] 5개 신규 테스트 파일 작성: test_orchestrator, test_protocol, test_cli, test_tmux, test_claude_agent
- [x] 테스트 결과 문서 작성: [`docs/test-results/phase-1-T.md`](test-results/phase-1-T.md)

### 커버리지 상세

| 모듈 | 커버리지 | 비고 |
|------|---------|------|
| `models.py` | 100% | |
| `orchestrator.py` | 100% | |
| `consensus.py` | 100% | |
| `distributor.py` | 100% | |
| `agents/base.py` | 100% | |
| `protocol.py` | 99% | 1줄 미커버 (unexpected type fallback) |
| `context/shared.py` | 98% | 2줄 미커버 |
| `agents/claude_agent.py` | 97% | InteractiveClaudeAgent stub (Phase 2) |
| `config.py` | 93% | tomli import 폴백 |
| `cli.py` | 86% | 에러 핸들링 경로 |
| `tmux/session.py` | 96% | |
| `tmux/pane.py` | 69% | send_text_heredoc (Phase 2에서 실제 tmux 필요) |

---

## Phase 2: tmux 인터랙티브 모드 — ✅ 완료

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

### 공유 파일 동시성 관련 설계 결정

**오케스트레이터 중앙 집중 쓰기 유지 (방안 1)**:
- Phase 2에서도 shared.md의 유일한 작성자는 Orchestrator
- 에이전트는 shared.md를 직접 읽지 않음
- Orchestrator가 에이전트 응답을 수집한 후 shared.md에 순차 기록
- 에이전트에게 이전 라운드 의견을 전달할 때는 프롬프트에 텍스트로 포함 (현재 `protocol.py:171-173`과 동일 방식)
- 결과: 파일 락 불필요, 동시성 문제 원천 차단

### 마일스톤

```
trinity ask "인증 시스템 설계해줘"
  → tmux 3분할 화면에 claude/codex/gemini가 각각 실행
  → 3라운드 토론이 pane에서 실시간으로 보임
  → 합의 도달 시 분담 결과가 각 pane에 전달
```

### 검증 완료

- [x] **완료 감지 모듈 구현** — `completion/` 하위 4개 파일: base, hook, prompt, idle
- [x] **FallbackChainDetector** — Hook→PromptReturn→Idle 순서로 동시 실행, 첫 성공 반환
- [x] **InteractiveClaudeAgent** — tmux pane에서 claude 실행, heredoc 프롬프트 주입, 응답 추출
- [x] **Orchestrator interactive 모드** — `TrinityOrchestrator(config, interactive=True)`, tmux 세션 생성, pane별 에이전트+감지기 할당
- [x] **CLI --interactive 플래그** — `trinity ask "질문" -i` 또는 `--interactive`
- [x] **Pane 타이틀 시각화** — DeliberationProtocol이 라운드 진행 상태를 pane 타이틀에 반영
- [x] **기존 테스트 134개 전부 통과** — Phase 2 코드가 Phase 1 기능에 영향 없음
- [x] **tmux 미사용 부채 해결** — InteractiveClaudeAgent가 tmux 레이어를 에이전트와 연결

---

## Phase 2-T: Phase 2 테스트 — ✅ 완료

### 목표
Phase 2에서 추가된 tmux 인터랙티브 모드 관련 모듈의 테스트를 작성한다.

### 구현해야 할 것

| 작업 | 파일 | 상세 |
|------|------|------|
| **InteractiveClaudeAgent 테스트** | `tests/test_interactive_claude.py` | start (tmux pane에서 claude 실행), send_and_wait (완료 감지 통합), graceful_shutdown, 역할 주입 |
| **완료 감지기 테스트** | `tests/test_completion.py` | IdleDetector: 출력 변화 감지, 타임아웃. PromptReturnDetector: 프롬프트 패턴 매칭. HookDetector: 파일 watch. Fallback 체인: Hook→PromptReturn→Idle 순서 |
| **tmux 통합 테스트** | `tests/test_tmux_integration.py` | 세션 생성→에이전트 실행→프롬프트 주입→응답 수집 전체 흐름 (tmux mock) |
| **Protocol 시각화 테스트** | `tests/test_protocol_v2.py` | pane 타이틀 업데이트, 라운드 진행 상태 반영 |

### 테스트 전략

```
tmux 의존 모듈:
  - subprocess.run을 mock하여 tmux CLI 없이 테스트
  - TmuxPane.capture()의 반환값을 mock하여 완료 감지 시뮬레이션

완료 감지기:
  - 각 Detector를 독립적으로 단위 테스트
  - Fallback 체인은 통합 테스트로 검증

통합:
  - tmux가 설치된 환경에서만 실행되는 마커 (@pytest.mark.tmux)
  - CI에서는 mock 모드로, 로컬에서는 실제 tmux로 선택적 실행
```

### 마일스톤

```
pytest tests/ -v --cov=trinity
  → 110+ 테스트 통과
  → completion/ 모듈 90%+ 커버리지
  → InteractiveClaudeAgent 80%+ 커버리지
```

### 결과 문서

테스트 완료 후 `docs/test-results/phase-2-T.md`에 다음 내용을 기록한다:

- 테스트 수, 통과/실패, 커버리지 수치
- 테스트 파일별 상세 결과 테이블
- 미커버 영역 분석 및 후속 조치
- 발견된 이슈 및 해결 내역

### 검증 완료

- [x] `pytest tests/ -v` → **190 passed** (기존 134개 → 56개 추가)
- [x] `pytest tests/ --cov=trinity` → **94% 커버리지** 유지
- [x] 4개 신규 테스트 파일: test_completion, test_interactive_claude, test_tmux_integration, test_protocol_v2
- [x] completion/idle.py, completion/prompt.py **100% 커버리지**
- [x] 테스트 중 버그 2개 발견 및 수정 (orchestrator 언패킹, mock side_effect)
- [x] 테스트 결과 문서: [`docs/test-results/phase-2-T.md`](test-results/phase-2-T.md)

---

## Phase 3: Context 모니터링 + 자동 세션 교체 — ✅ 완료

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
    2. shared.md에 세션 히스토리 추가
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

### 검증 완료

- [x] **ContextMonitor** (`context/monitor.py`) — Provider별 토큰 카운트 파싱, configurable 임계값, Claude/Codex/Gemini 파서
- [x] **SessionRotator** (`context/rotator.py`) — 요약 요청→shared.md 기록→세션 종료→새 세션 시작(요약+shared.md 주입)
- [x] **Orchestrator 연동** — `_check_and_rotate()` 호출, 브로드캐스트 알림, 에러 복구
- [x] **합의 판정 개선** — 부정어 필터링(disagree, don't agree, oppose, against 등), 문장 단위 독립 판정
- [x] 기존 테스트 190개 전부 통과 — Phase 3 코드가 이전 기능에 영향 없음
- [x] 세션 교체 미구현 부채 해결

---

## Phase 3-T: Phase 3 테스트 — ✅ 완료

### 목표
Phase 3에서 추가된 Context 모니터링 및 세션 교체 관련 모듈의 테스트를 작성한다.

### 구현해야 할 것

| 작업 | 파일 | 상세 |
|------|------|------|
| **ContextMonitor 테스트** | `tests/test_context_monitor.py` | 토큰 카운트 파싱 (Claude JSON, Codex 세션 파일, Gemini 출력), 임계값 체크, Provider별 기본값 |
| **SessionRotator 테스트** | `tests/test_session_rotator.py` | 전체 교체 플로우 (요청→요약→종료→재시작), keep_sections 보존 검증, 브로드캐스트 알림 |
| **keep_sections 통합 테스트** | `tests/test_session_handoff.py` | 세션 교체 후 새 세션의 첫 프롬프트에 pinned 섹션 포함 확인, 최근 N라운드 포함 확인 |
| **합의 판정 개선 테스트** | `tests/test_consensus_v2.py` | LLM 판정 (mock) / 정형 출력 파싱, false positive 제거 ("disagree"가 agree로 매칭 안 되는지) |

### 마일스톤

```
pytest tests/ -v --cov=trinity
  → 140+ 테스트 통과
  → context/ 모듈 85%+ 커버리지
  → 세션 교체 플로우 E2E 테스트 포함
```

### 검증 완료

- [x] `pytest tests/ -v` → **234 passed** (기존 190개 → 44개 추가)
- [x] `pytest tests/ --cov=trinity` → **94% 커버리지** 유지
- [x] 4개 신규 테스트 파일: test_context_monitor, test_session_rotator, test_session_handoff, test_consensus_v2
- [x] context/monitor.py **98%**, context/rotator.py **96%**, consensus.py **100%** 커버리지
- [x] "disagree" false positive 해결 확인 — negation 필터링 테스트 통과
- [x] 테스트 결과 문서: [`docs/test-results/phase-3-T.md`](test-results/phase-3-T.md)

### 결과 문서

테스트 완료 후 `docs/test-results/phase-3-T.md`에 다음 내용을 기록한다:

- 테스트 수, 통과/실패, 커버리지 수치
- 테스트 파일별 상세 결과 테이블
- 미커버 영역 분석 및 후속 조치
- 발견된 이슈 및 해결 내역

---

## Phase 4: 다중 Provider + 헬스체크 — ✅ 완료

### 목표
Codex, Gemini CLI를 네이티브로 지원하고 에이전트 간 헬스체크 구현.

### 구현한 것

| 작업 | 파일 | 상태 | 상세 |
|------|------|------|------|
| **CodexAgent** | `agents/codex_agent.py` | ✅ | Codex CLI 제어: 세션 파일 탐색, 폴링, print/interactive 모드 |
| **GeminiAgent** | `agents/gemini_agent.py` | ✅ | Gemini CLI 제어: idle 타임아웃, 마커 주입, 하드 타임아웃 |
| **AgentFactory** | `agents/factory.py` | ✅ | config → provider별 에이전트 인스턴스 생성, detector 체인 생성 |
| **HealthChecker** | `health/checker.py` | ✅ | 동기/비동기 health check, ping, 주기적 모니터링 |
| **Provider별 완료 감지 분리** | `completion/` 하위 | ✅ | Claude/Codex/Gemini 각각 전용 detector chain |
| **Workspace 격리** | `workspace/isolation.py` | ✅ | git-worktree 생성/관리/병합 (.trinity/workspace/<agent>/) |
| **Managed Home** | `workspace/managed_home.py` | ✅ | 에이전트별 격리 홈, env override, 설정 파일 관리 |

### Provider별 완료 감지 체인

| Provider | 체인 구성 | 특징 |
|----------|----------|------|
| **Claude Code** | Hook → PromptReturn → Idle(10s) | 가장 안정적, Hook 기반 |
| **Codex** | PromptReturn($, >) → Idle(15s) | 세션 프롬프트 패턴 |
| **Gemini CLI** | Idle(20s) → PromptReturn | Idle이 주 감지기 |

### 검증 완료

- [x] **CodexAgent** — print/interactive 모드, 세션 JSON 파싱, 토큰 카운트
- [x] **GeminiAgent** — completion marker 주입, 하드 타임아웃, 토큰 카운트 정규식
- [x] **AgentFactory** — provider별 에이전트 생성, detector 체인 생성
- [x] **HealthChecker** — 동기/비동기 check_all, ping, start_monitoring
- [x] **WorkspaceIsolation** — worktree 생성/삭제/병경, 변경 사항 감지
- [x] **ManagedHome** — 격리 홈, env override, 설정 파일 I/O
- [x] Orchestrator에 Phase 4 컴포넌트 연동
- [x] 기존 테스트 234개 전부 통과 — Phase 4 코드가 이전 기능에 영향 없음

---

## Phase 4-T: Phase 4 테스트 — ✅ 완료

### 목표
Phase 4에서 추가된 다중 Provider 지원, 헬스체크, 워크스페이스 격리 관련 모듈의 테스트를 작성한다.

### 구현한 것

| 작업 | 파일 | 상세 |
|------|------|------|
| **CodexAgent 테스트** | `tests/test_codex_agent.py` | 19 tests: 세션 파일 탐색, print 모드, 토큰 카운트 파싱 |
| **GeminiAgent 테스트** | `tests/test_gemini_agent.py` | 21 tests: 마커 주입, 하드 타임아웃, 토큰 카운트 정규식 |
| **AgentFactory 테스트** | `tests/test_agent_factory.py` | 16 tests: provider별 에이전트 생성, detector 체인 구조 |
| **HealthChecker 테스트** | `tests/test_health_checker.py` | 19 tests: 동기/비동기 check, ping, 모니터링 루프 |
| **Workspace 격리 테스트** | `tests/test_workspace.py` | 28 tests: worktree 생성/삭제, 브랜치 관리, 병합, 변경 감지 |
| **Managed Home 테스트** | `tests/test_managed_home.py` | 26 tests: 격리 홈, env override, 설정 I/O, 디스크 사용량 |
| **다중 Provider 통합 테스트** | `tests/test_multi_provider.py` | 23 tests: 3-provider 동시 생성, 컴포넌트 연동, 상태/예산 검증 |

### 검증 완료

- [x] `pytest tests/ -v` → **386 passed** (기존 234개 → 152개 추가)
- [x] `pytest tests/ --cov=trinity` → **91% 커버리지**
- [x] 7개 신규 테스트 파일 작성
- [x] workspace/isolation.py **97%**, workspace/managed_home.py **95%** 커버리지
- [x] 테스트 결과 문서: [`docs/test-results/phase-4-T.md`](test-results/phase-4-T.md)

---

## Phase 5: 프로덕션 폴리싱 — ✅ 완료

### 구현한 것

| 작업 | 파일 | 상세 |
|------|------|------|
| `trinity attach` | `cli.py` | tmux 세션에 attach |
| `trinity logs --follow` | `cli.py` | 오케스트레이터 로그 실시간 출력 |
| `trinity config <key>` | `cli.py` | 설정 값 조회 |
| `trinity reset --keep-context` | `cli.py` | 세션 초기화 (shared.md 보존 옵션) |
| `trinity status-watch` | `cli.py` | 실시간 상태 대시보드 (Live) |
| **재시도 로직** | `retry.py` | RetryConfig: 종료 코드 + 출력 패턴 기반, 지수 백오프, jitter |
| **에러 핸들링** | `error_handler.py` | Provider 크래시 → 자동 respawn, 컨텍스트 주입, 비활성화 정책 |
| **로깅 개선** | `logging.py` | 파일 로깅 + Rich 콘솔 포맷팅, 레벨 필터링 |

### 검증 완료

- [x] **RetryConfig** — 지수 백오프, jitter, 종료 코드/패턴/예외 기반 재시도 판정
- [x] **ErrorHandler** — 크래시 기록, 자동 respawn, 컨텍스트 주입, 비활성화 임계값
- [x] **로깅** — Rich 콘솔 + 파일 동시 출력, 디렉토리 자동 생성
- [x] **CLI** — attach, logs, config, reset, status-watch 5개 명령어 추가
- [x] 기존 테스트 386개 전부 통과 — Phase 5 코드가 이전 기능에 영향 없음

---

## Phase 5-T: Phase 5 테스트 — ✅ 완료

### 구현한 것

| 작업 | 파일 | 상세 |
|------|------|------|
| **재시도 로직 테스트** | `tests/test_retry.py` | 24 tests: 지수 백오프, jitter, 종료 코드/패턴/예외 판정, async/sync 실행 |
| **에러 핸들링 테스트** | `tests/test_error_handling.py` | 17 tests: 크래시 기록, 비활성화, respawn, 콜백, 리셋 |
| **CLI 추가 명령어 테스트** | `tests/test_cli_v2.py` | 10 tests: config, logs, reset, attach, status-watch |
| **로깅 테스트** | `tests/test_logging.py` | 10 tests: 파일/콘솔 핸들러, 포맷, 레벨, 자식 Logger |
| **E2E 시나리오 테스트** | `tests/test_e2e.py` | 8 tests: init → status → ask → context → version |

### 검증 완료

- [x] `pytest tests/ -v` → **455 passed** (기존 386개 → 69개 추가)
- [x] `pytest tests/ --cov=trinity` → **90% 커버리지**
- [x] 5개 신규 테스트 파일 작성
- [x] E2E 시나리오로 init → ask → status → context 전체 흐름 검증
- [x] 테스트 결과 문서: [`docs/test-results/phase-5-T.md`](test-results/phase-5-T.md)

---

## Phase 6: 인터랙티브 설정 + Terminal UI — ✅ 완료

### 구현한 것

| 작업 | 파일 | 상세 |
|------|------|------|
| **CLI 자동 감지** | `setup/detector.py` | `claude --version`, `codex --version`, `gemini --version` 실행, 설치 여부/버전/경로 감지 |
| **인터랙티브 설정 위자드** | `setup/wizard.py` | Rich 기반 4단계 위자드: 감지 → 선택 → 커스터마이징 → 리뷰 |
| **TUI 애플리케이션** | `tui/app.py` | Rich Live 기반: 헤더, 에이전트 상태, 토론 진행, 결과 패널 |
| **인터랙티브 세션** | `tui/session.py` | 입력 루프 + /명령어 + 실시간 Rich Live 업데이트 |
| **tmux TUI 레이아웃** | `tmux/layout.py` | 상단 TUI + 하단 에이전트 분할 레이아웃 |
| **CLI 업그레이드** | `cli.py` | `trinity` 단독 실행 → TUI 진입, `init` → 인터랙티브 위자드, `--non-interactive` 플래그 |

### 검증 완료

- [x] `pytest tests/ -v` → **571 passed** (기존 454개 → 117개 추가)
- [x] `pytest tests/ --cov=trinity` → **87% 커버리지**
- [x] 5개 신규 테스트 파일: test_cli_detector, test_setup_wizard, test_tui, test_tui_session, test_tmux_layout
- [x] 기존 454개 테스트 호환성 유지
- [x] 테스트 결과 문서: [`docs/test-results/phase-6-T.md`](test-results/phase-6-T.md)

### CLI 변경 사항

| 명령어 | 변경 |
|--------|------|
| `trinity` | 단독 실행 시 인터랙티브 TUI 모드 진입 (신규) |
| `trinity init` | 인터랙티브 설정 위자드 (CLI 감지 + 에이전트 선택) |
| `trinity init --non-interactive` | 기존 동작 (기본값으로 바로 생성) |

### TUI 명령어 모드

| 명령어 | 설명 |
|--------|------|
| `질문 텍스트` | 에이전트에게 토론 주제 전달 |
| `/status` | 에이전트 상태 테이블 표시 |
| `/context` | 공유 컨텍스트(shared.md) 표시 |
| `/rounds [N]` | 최대 라운드 수 변경 |
| `/agent <name> on/off` | 특정 에이전트 활성화/비활성화 |
| `/history` | 이전 토론 기록 표시 |
| `/save` | 현재 세션 결과 저장 |
| `/quit` | 종료 |

---

## Phase 6-T: Phase 6 테스트 — ✅ 완료

### 검증 완료

- [x] `pytest tests/ -v` → **571 passed** (기존 454개 → 117개 추가)
- [x] `pytest tests/ --cov=trinity` → **87% 커버리지**
- [x] 5개 신규 테스트 파일 작성
- [x] 테스트 결과 문서: [`docs/test-results/phase-6-T.md`](test-results/phase-6-T.md)

---

## Post-6 핫픽스

### surrogate 문자 인코딩 크래시 수정 — ✅ 완료

**문제**: 사용자 입력 또는 tmux capture-pane 출력에 포함된 **서로게이트 코드포인트**(U+D800–U+DFFF)가 `SharedContextEngine.write()`에서 `UnicodeEncodeError: 'utf-8' codec can't encode characters: surrogates not allowed` 크래시를 유발.

**원인**: Python이 터미널/tmux에서 유효하지 않은 UTF-8 바이트를 읽을 때 `surrogateescape` 핸들러로 이를 서로게이트 코드포인트로 변환. 이후 `write_text(encoding="utf-8")`로 쓸 때 서로게이트는 UTF-8로 인코딩할 수 없어 크래시.

**수정**:
- `src/trinity/context/shared.py` — `_sanitize()` 정적 메서드 추가: `encode("utf-8", errors="replace").decode("utf-8")`로 서로게이트를 `?`로 치환
- `write()`에서 `_sanitize()` 호출하여 모든 쓰기 경로에서 서로게이트 문제 해결

**테스트**: 4개 신규 테스트 추가 (600 passed, 기존 596 → 4개 추가)

| 테스트 | 검증 내용 |
|--------|-----------|
| `test_write_surrogate_characters` | `initialize()`가 서로게이트 포함 프롬프트 처리 |
| `test_write_section_with_surrogates` | `write_section()`이 서로게이트 포함 내용 처리 |
| `test_append_opinion_with_surrogates` | `append_opinion()`이 서로게이트 포함 에이전트 출력 처리 |
| `test_sanitize_preserves_valid_utf8` | 정상 한글·이모지는 변경 없이 보존 |

### init 언어 선택 기능 (i18n) — ✅ 완료

**요구사항**: `trinity init` 시 언어(영어/한국어)를 선택하고, 그에 맞는 역할 프롬프트와 마법사 UI 제공.

**구현**:
- `src/trinity/i18n.py` (신규) — `Strings` 데이터클래스 + EN/KO 문자열 번들 + 역할 프롬프트
- `src/trinity/setup/wizard.py` — Step 0 `_step_language()` 추가, 모든 하드코딩 영어 문자열 → `get_strings(self.lang)` 참조로 교체
- `src/trinity/setup/detector.py` — `get_provider_role(provider, lang)` 함수 추가
- `src/trinity/config.py` — `default_config(lang="en")` 매개변수 추가
- `src/trinity/cli.py` — `_init_interactive()` 요약 패널 현지화

**한국어 역할 프롬프트**:
| 에이전트 | 한국어 역할 |
|----------|------------|
| claude | 당신은 아키텍트입니다. 시스템을 설계하고 코드를 리뷰하며... |
| codex | 당신은 구현자입니다. 아키텍처 결정에 기반하여 깔끔하고 효율적인 코드를... |
| gemini | 당신은 리뷰어입니다. 대안을 탐색하고 잠재적인 문제를 식별하며... |

**테스트**: 22개 신규 테스트 (test_i18n.py), 622 passed
**하위호환**: `--non-interactive` 모드는 영어 기본값 유지

---

## Phase 7: 프롬프트 압축 — ✅ 완료

### 목표
토론 라운드가 진행될수록 프롬프트가 선형적으로 커지는 문제를 해결. 오래된 라운드를 자동으로 압축하여 토큰 사용량을 최대 79% 절감.

### 구현한 것

| 작업 | 파일 | 상세 |
|------|------|------|
| **압축 설정** | `config.py` | `prompt_compression_enabled`, `prompt_compression_round_threshold`, `prompt_compression_max_summary_tokens` |
| **휴리스틱 압축기** | `context/compressor.py` (신규) | `PromptCompressor`: 키워드 기반 문장 추출, 한/영 25개 키워드, CJK 토큰 추정 |
| **압축 섹션 저장** | `context/shared.py` | `write_compressed_summary()`, `get_rounds_for_prompt()` |
| **프로토콜 통합** | `deliberation/protocol.py` | `_build_round_prompt()` 압축 사용, `_compress_old_rounds()`, `_extract_agent_opinions()` |
| **설정 전달** | `orchestrator.py` | TrinityConfig → DeliberationProtocol 압축 설정 와이어링 |

### 작동 방식

```
Round 1: "User's request: {prompt}"                    ← 변경 없음
Round 2: "Previous opinions:\n{Round 1 전체}"          ← 변경 없음
Round 3+: "요약된 과거:\n{compressed}\n최근:\n{full}"  ← NEW!
```

- Round ≥ `compression_round_threshold`(기본 2)부터 오래된 라운드 자동 압축
- 직전 라운드(N-1)는 verbatim 유지 (정확한 토론 보장)
- 그 이전 라운드는 키워드 기반 문장 추출로 요약
- `prompt_compression_enabled=false`로 비활성화 가능

### 토큰 절감 효과 (추정)

| 시나리오 | Before | After | 절감 |
|----------|--------|-------|------|
| Round 3 (3 에이전트) | ~3,900 tokens | ~2,100 tokens | **46%** |
| Round 5 (3 에이전트) | ~5,800 tokens | ~2,400 tokens | **59%** |
| Round 5 (10라운드 세션) | ~15,000 tokens | ~3,200 tokens | **79%** |

### 검증 완료

- [x] **TDD**: 각 Task마다 테스트 먼저 작성 → 실패 확인 → 구현
- [x] `pytest tests/ -v` → **640 passed** (기존 622개 → 18개 추가)
- [x] 기존 622개 테스트 전부 통과 — 회귀 없음
- [x] 5개 커밋 (Task별 1개)
- [x] 테스트 결과 문서: [`docs/test-results/phase-7-T.md`](test-results/phase-7-T.md)

---

## 아키텍처 부채 (현재 알려진 것)

| 항목 | 심각도 | 설명 | 해결 시점 |
|------|--------|------|-----------|
| ~~키워드 합의 판정~~ | ~~높음~~ | ~~"I disagree"에도 "agree"가 매칭됨 (테스트에서 확인)~~ | **✅ 해결: Phase 3에서 부정어 필터링으로 false positive 제거** |
| ~~단일 Provider 의존~~ | ~~높음~~ | ~~Codex/Gemini이 Claude print mode로 폴백~~ | **✅ 해결: Phase 4에서 CodexAgent, GeminiAgent 네이티브 구현** |
| ~~공유 파일 동시성~~ | ~~중간~~ | ~~두 에이전트가 동시에 shared.md 쓰면 충돌 가능~~ | **✅ 해결: 오케스트레이터 중앙 집중 쓰기로 원천 차단** |
| ~~테스트 부족~~ | ~~중간~~ | ~~orchestrator, protocol, CLI 테스트 없음~~ | **✅ 해결: Phase 1-T에서 134 테스트, 94% 커버리지 달성** |
| ~~세션 교체 미구현~~ | ~~중간~~ | ~~ContextUsage 모델만 있고 자동 교체 없음~~ | **✅ 해결: Phase 3에서 ContextMonitor + SessionRotator 구현** |
| ~~tmux 미사용~~ | ~~낮음~~ | ~~Phase 1은 서브프로세스만, tmux 레이어가 연결 안 됨~~ | **✅ 해결: Phase 2에서 InteractiveClaudeAgent로 tmux 연결** |

---

## Phase 8: Caveman 출력 압축 통합 — ✅ 완료

### 배경

[Caveman](https://github.com/JuliusBrussee/caveman)은 AI 에이전트의 출력에서 불필요한 말을 제거하여 **65-75% 토큰 절감**을 달성하는 크로스 플랫폼 플러그인. Trinity의 에이전트가 Caveman 스타일로 응답하면 토론 전체의 토큰 비용이 크게 감소.

Trinity는 에이전트에 보내는 **모든 프롬프트를 완전히 제어**하므로, Caveman처럼 별도 hook을 설치할 필요 없이 프롬프트에 압축 규칙을 추가하는 것만으로 통합 가능.

### 설계 결정

- **기본 활성화**: `caveman_mode=True`, `caveman_intensity="full"` — init 시 질문 없이 바로 적용
- **3단계 강도**: `lite`(미사여구만 제거) / `full`(관사/파편화/짧은동의어) / `ultra`(축약어/화살표/최대압축)
- **이중 주입**: 역할 프롬프트에 규칙 부착 + 매 턴 per-turn reinforcement (드리프트 방지)
- **런타임 토글**: TUI `/caveman` 명령어로 실시간 on/off/강도 변경

### 구현한 것

| 작업 | 파일 | 상세 |
|------|------|------|
| **Caveman 규칙** | `i18n.py` | `CAVEMAN_RULES` (3강도), `CAVEMAN_REINFORCEMENT` (per-turn), `get_agent_prompt()`, `localized_roles_with_caveman()` |
| **설정 필드** | `config.py` | `caveman_mode: bool = True`, `caveman_intensity: str = "full"`, TOML `[context]` 섹션에 저장 |
| **Per-turn 강화** | `deliberation/protocol.py` | `_append_caveman()` — 매 라운드 프롬프트에 압축 리마인더 추가 |
| **설정 전달** | `orchestrator.py` | `TrinityConfig.caveman_*` → `DeliberationProtocol(caveman_mode=, caveman_intensity=)` |
| **마법사 연동** | `setup/wizard.py` | `localized_roles_with_caveman()`로 caveman 포함 역할 프롬프트 사용 |
| **TUI 명령어** | `tui/session.py` | `/caveman [on\|off\|lite\|full\|ultra]` — 런타임 실시간 토글 |
| **TUI 뱃지** | `tui/app.py` | 헤더에 `🦴 CAVEMAN:FULL` 상태 뱃지 표시 |

### 프롬프트 주입 흐름

```
Agent Role Prompt (세션 시작 시 1회):
  "You are the Architect. You design systems..."

  + [Output Style] Drop articles (a, an, the), filler, hedging...   ← Caveman 규칙

Round Prompt (매 턴):
  "Previous round opinions: ..."

  + [Caveman: respond in compressed style. No articles, no filler...]  ← Per-turn 강화
```

### TOML 설정

```toml
[context]
caveman_mode = true
caveman_intensity = "full"    # lite | full | ultra
```

### 검증 완료

- [x] 기본값 `caveman_mode=True` + `caveman_intensity="full"` 동작 확인
- [x] 역할 프롬프트에 `[Output Style]` 규칙 자동 부착 확인
- [x] `_build_round_prompt()`에 per-turn 강화 추가 확인
- [x] `/caveman` TUI 명령어 on/off/강도 변경 동작
- [x] 기존 671 테스트 전부 통과 — 회귀 없음
- [x] `pip install trinity-agent==0.6.0` 배포 완료

---

## Phase 9: TUI/UX 대수선 — ✅ 완료

### 목표

v0.6.0 실사용에서 발견된 6가지 치명적 UX 결함을 수정하여 TUI를 프로덕션 수준으로 끌어올린다.

### 배경

사용자가 `uv run trinity`로 실제 질문("이더 스캔에서 고래 추적 봇 설계")을 던졌을 때,
에이전트 응답이 CLI 스플래시 화면과 뒤섞여 알아볼 수 없었고, 합의 후 세션이 멈추며,
방향키 입력이 깨지는 등 기본적인 인터랙션이 불가능했다.

### 해결한 문제

| # | 문제 | 원인 | 해결 |
|---|------|------|------|
| **P1** | 세션 멈춤 | `_run_with_live()`가 스레드 종료만 대기, 타임아웃 없음 | 5분 하드 리미트 + `DELIBERATION_DONE` 이벤트 즉시 종료 |
| **P2** | 출력 왜곡 | tmux 캡처 시 CLI 스플래시/배너가 응답에 포함 | `ResponseCleaner` 정제 파이프라인 신규 추가 |
| **P3** | 언어 미반영 | 프로토콜 라운드 프롬프트가 항상 영어 | `config.lang` → `protocol.lang` → `i18n.ROUND_PROMPTS` |
| **P4** | 글자수 제한 | 80/500자 하드코딩 | 터미널 너비 기반 동적 계산 (최소 800자) |
| **P5** | 테이블 깨짐 | Rich Table이 터미널 너비 초과 → 줄바꿈 | 파일럿 뷰 + 카드 레이아웃 + 간단 리스트 |
| **P6** | 방향키 깨짐 | `Prompt.ask()` → `input()`은 라인 편집 불가 | `prompt_toolkit` 도입 (히스토리, 커서, Tab) |

### 구현된 것

| 컴포넌트 | 파일 | 상태 | 설명 |
|----------|------|------|------|
| **응답 정제기** | `src/trinity/agents/response_cleaner.py` | ✅ 신규 | CLI 스플래시/배너/패턴 블랙리스트 제거 |
| **프롬프트 세션** | `src/trinity/tui/prompt.py` | ✅ 신규 | prompt_toolkit 기반 입력 (방향키, 히스토리, 자동완성) |
| **에이전트 수정** | `claude_agent.py`, `codex_agent.py`, `gemini_agent.py` | ✅ 수정 | `_extract_response()`에 ResponseCleaner 적용 |
| **설정 언어** | `src/trinity/config.py` | ✅ 수정 | `lang` 필드 추가, TOML 읽기/쓰기 |
| **라운드 i18n** | `src/trinity/i18n.py` | ✅ 수정 | `ROUND_PROMPTS` en/ko, `get_round_prompt()` |
| **프로토콜 현지화** | `src/trinity/deliberation/protocol.py` | ✅ 수정 | `lang` 매개변수, `_build_round_prompt()` 현지화 |
| **오케스트레이터** | `src/trinity/orchestrator.py` | ✅ 수정 | `config.lang` → protocol 전달 |
| **TUI 레이아웃** | `src/trinity/tui/app.py` | ✅ 수정 | 파일럿 뷰, 동적 글자수, 리스트 작업 분배 |
| **세션 루프** | `src/trinity/tui/session.py` | ✅ 수정 | 타임아웃 가드, prompt_toolkit, 단순 결과 표시 |
| **의존성** | `pyproject.toml` | ✅ 수정 | `prompt_toolkit>=3.0` 추가 |

### 데이터 흐름 (언어)

```
trinity init → lang="ko"
  → TrinityConfig.lang = "ko" → TOML 저장
  → ROLE_PROMPTS["ko"] → AgentSpec.role_prompt (기존)

trinity run → config.lang="ko" 로드
  → TrinityOrchestrator → DeliberationProtocol(lang="ko")
  → _build_round_prompt()
    → i18n.get_round_prompt("round1_prefix", "ko", prompt=...)
    → "아래 공유 컨텍스트를 배경으로 읽으세요.\n사용자 요청: ..."
```

### 검증 완료

- [x] **690 테스트 통과** (671 → 690, 신규 20개)
- [x] ResponseCleaner 12개 테스트 — Claude/Codex/Gemini 스플래시 제거 검증
- [x] TrinityPromptSession 8개 테스트 — 히스토리, 완성, 예외 전파 검증
- [x] 기존 테스트 전부 통과 — 회귀 없음
- [x] 설계 문서 → `docs/plans/2026-06-02-tui-overhaul.md`
- [x] 테스트 결과 → `docs/test-results/phase-9-T.md`

### 후속 핫픽스 (v0.6.1~0.6.4)

실사용 테스트에서 발견된 문제를 3차례 패치로 해결:

| 버전 | 문제 | 해결 |
|------|------|------|
| v0.6.2 | Live 중 스플래시 여전히 표시 | `build_deliberation_panel()` 내용 렌더링 완전 차단, 상태만 표시 |
| v0.6.3 | 타임아웃 시 `NoneType` 크래시 | `_run_deliberation()` None 가드 + 모든 에러 경로 `reset_agents()` |
| v0.6.4 | 응답 추출 실패 (line-count 불일치) | `_extract_response_from_pane()` 전체 패널 재캡처 + 절대 줄 경계 |
| v0.6.4 | 기존 TOML에 `lang` 없어 영어 응답 | `_detect_lang_from_agents()` role_prompt 한글 감지 자동 설정 |

### 후속 핫픽스 (v0.6.9)

| 문제 | 해결 |
|------|------|
| Windows 비대화형 테스트 환경에서 `prompt_toolkit`이 콘솔 버퍼를 찾지 못해 `NoConsoleScreenBufferError` 발생 | `TrinityPromptSession` 생성 시 정상 콘솔을 우선 사용하고, 콘솔 버퍼가 없을 때만 dummy input/output으로 fallback |
| README와 설정 템플릿이 현재 코드 기본값과 불일치 | 테스트 수, 버전, `lang`, 프롬프트 압축, Caveman 설정을 현재 v0.6.9 기준으로 갱신 |

**검증**: `uv run pytest -q` → **743 passed** (경고 1건: mock 관련 RuntimeWarning)
**결과 문서**: [`docs/test-results/phase-10-T.md`](test-results/phase-10-T.md)

---

## Post-10: 모델 선택 기반 컨텍스트 예산 설정 — ✅ 완료

### 목표
`trinity init`에서 provider 기본 예산만 보여주던 한계를 보완하여, 사용자가 각 에이전트의 모델을 선택하면 해당 모델의 컨텍스트 예산을 config에 저장한다.

### 구현한 것

| 작업 | 파일 | 상세 |
|------|------|------|
| **모델 registry** | `src/trinity/models.py` | Claude/Codex/Gemini 모델별 context budget 메타데이터와 provider 기본 모델 정의 |
| **AgentSpec 모델 필드** | `src/trinity/models.py`, `src/trinity/config.py` | `model` 필드 저장/로드, 알려진 모델이면 `effective_context_budget`에 반영 |
| **CLI 모델 전달** | `src/trinity/agents/*_agent.py`, `src/trinity/agents/base.py` | `model != "default"`이면 provider 실행 명령에 `--model <model>` 자동 추가 |
| **init 모델 선택** | `src/trinity/setup/wizard.py`, `src/trinity/i18n.py` | Step 3에서 모델 선택/직접 입력을 제공하고 선택된 budget을 표시 |
| **문서/템플릿** | `README.md`, `README.en.md`, `templates/trinity.config.example` | `model`과 `context_budget` 예시 갱신 |

### 검증 완료

- [x] `uv run pytest -q` → **758 passed** (경고 1건: mock 관련 RuntimeWarning)
- [x] 변경 파일 대상 `ruff check` 통과

---

## Phase 11 / v0.7.0: Multi-Agent Workflow Engine 재설계 — 📋 계획 수립

### 배경

실사용 interactive smoke에서 "레이어2 체인 간 브릿지 경로 탐색 봇 설계" 요청을 실행했을 때, Trinity가 실제 설계 합의를 만들지 못하고 provider 인증/초기화 UI를 응답으로 캡처하는 문제가 확인되었다.

관찰된 문제:

| Agent | 관찰된 상태 | 영향 |
|-------|-------------|------|
| Claude | OAuth URL, invalid code, retry 화면 | ready 상태가 아닌데 deliberation에 투입됨 |
| Codex | `gpt-5.5 default`, `/model to change`, CLI 배너 | 실제 답변 대신 CLI noise가 캡처됨 |
| Gemini | 인증 방식 선택/Vertex env 안내 화면 | 인증 대기 UI가 응답으로 캡처됨 |

최종 결과는 `No usable consensus after 5 rounds`, `Tokens: 0`이었다. 이는 Phase 10 provider reliability가 아직 완전히 해결되지 않았고, 동시에 Trinity의 상위 흐름이 단발성 deliberation protocol에서 workflow engine으로 확장되어야 함을 보여준다.

### v0.7.0 사용자 목표

사용자가 원하는 동작:

1. 등록된 1~3개 에이전트가 설계/기획을 상호 수정하며 하나의 결론을 만든다.
2. 사용자 의사결정이 필요하면 다음 채팅에서 질의응답을 반복한다.
3. 결론이 확정되면 큰 설계도를 에이전트 수만큼 work package로 분해한다.
4. 각 에이전트는 할당받은 일을 수행하고 필요하면 내부 subagent/tool에 위임한다.
5. 실행 중 변경사항과 의사결정은 공유문서에 기록한다.
6. 전체 과정은 상태 기반 loop로 진행된다.
7. 모든 단계에서 context 사용량과 세션 상태를 감시하고, 임계치 도달 시 요약 후 새 세션으로 이어간다.

### 핵심 재설계 항목

| 우선순위 | 항목 | 목표 |
|----------|------|------|
| P0 | Provider readiness/auth gating | 인증/모델 로딩/CLI 배너 상태에서는 deliberation을 시작하지 않음 |
| P0 | Interactive response contract | raw output과 clean response를 분리하고 request boundary 기반 추출을 강화 |
| P1 | Workflow state machine | `DELIBERATING`, `NEEDS_USER_DECISION`, `EXECUTING` 등 상태 기반 진행 |
| P1 | Structured deliberation | plain text consensus 대신 blueprint/open question/decision 구조 생성 |
| P1 | User decision loop | 사용자 답변을 새 prompt가 아니라 pending question 답변으로 처리 |
| P1 | Blueprint decomposition | 확정 설계를 active agent 수만큼 work package로 분해 |
| P1 | Execution protocol | task assignment를 실제 agent 실행으로 연결 |
| P2 | Subagent delegation policy | provider 내부 subagent/tool 사용 결과를 parent agent report로 추적 |
| P2 | Shared decision ledger | shared.md와 workflow JSON state를 분리 저장 |
| P2 | Lifecycle rotation everywhere | deliberation/execution/user decision 전체에서 context rotation 수행 |

### 계획 문서

상세 설계:

- [`docs/plans/2026-06-03-v0.7.0-workflow-engine-redesign.md`](plans/2026-06-03-v0.7.0-workflow-engine-redesign.md)

### 완료 기준 초안

- [ ] Provider readiness 실패 시 명확한 사용자 조치와 함께 workflow 시작 차단
- [ ] 1/2/3 active agent별 structured blueprint 합의
- [ ] 사용자 의사결정 질문 생성/답변/재개 loop
- [ ] blueprint에서 agent별 work package 생성
- [ ] execution intent에서 실제 agent call 수행
- [ ] shared.md에 decisions/open questions/work packages/task results 기록
- [ ] workflow state를 `.trinity/workflow/session.json`에 저장/복구
- [ ] context threshold가 round 전후와 execution package 전후에 감시됨
- [ ] WSL/tmux 실제 smoke 결과 문서 작성

---

## Phase 7B: 토큰 최적화 — 정리, 추정, 인터랙티브 카운팅 — ✅ 완료

### 목표
Phase 7의 프롬프트 압축에 이어 세 가지 추가 토큰 최적화: (1) 압축 후 오래된 라운드 섹션 자동 삭제, (2) 프롬프트 전송 전 토큰 예산 검사, (3) InteractiveClaudeAgent 누적 토큰 카운팅.

### 구현한 것

| 작업 | 파일 | 상세 |
|------|------|------|
| **섹션 삭제** | `context/shared.py` | `remove_section()` — shared.md에서 ## 섹션 제거 |
| **압축 후 자동 정리** | `deliberation/protocol.py` | `_compress_old_rounds()`에서 압축 후 원본 Opinion 섹션 삭제 |
| **토큰 예산 검사기** | `context/budget.py` (신규) | `TokenBudgetChecker`: 전송 전 토큰 추정, 안전/경고/위험 판정 |
| **프로토콜 통합** | `deliberation/protocol.py` | `budget_checker` 속성으로 예산 검사기 인스턴스 보유 |
| **인터랙티브 누적 카운팅** | `agents/claude_agent.py` | `InteractiveClaudeAgent.send_and_wait()`에서 토큰 누적 (리셋 방지) |

### 검증 완료

- [x] `pytest tests/ -q` → **655 passed** (기존 640개 → 15개 추가)
- [x] 5개 커밋 (Task별 1개)
- [x] 기존 테스트 회귀 없음

---

## 전체 Phase 로드맵 요약

```
Phase 1   ✅ 최소 작동 프로토타입 (완료)
Phase 1-T ✅ Phase 1 누락 테스트 보충 (134 테스트, 94% 커버리지) → docs/test-results/phase-1-T.md
Phase 2   ✅ tmux 인터랙티브 모드 (완료)
Phase 2-T ✅ Phase 2 테스트 (190 테스트, 94% 커버리지) → docs/test-results/phase-2-T.md
Phase 3   ✅ Context 모니터링 + 자동 세션 교체 (완료)
Phase 3-T ✅ Phase 3 테스트 (234 테스트, 94% 커버리지) → docs/test-results/phase-3-T.md
Phase 4   ✅ 다중 Provider + 헬스체크 + 워크스페이스 격리 (완료)
Phase 4-T ✅ Phase 4 테스트 (386 테스트, 91% 커버리지) → docs/test-results/phase-4-T.md
Phase 5   ✅ 프로덕션 폴리싱 (완료)
Phase 5-T ✅ Phase 5 테스트 (455 테스트, 90% 커버리지) → docs/test-results/phase-5-T.md
Phase 6   ✅ 인터랙티브 설정 + TUI (완료)
Phase 6-T ✅ Phase 6 테스트 (571 테스트, 87% 커버리지) → docs/test-results/phase-6-T.md
Phase 7   ✅ 프롬프트 압축 (완료) → docs/test-results/phase-7-T.md
Phase 7B  ✅ 토큰 최적화 — 정리, 추정, 인터랙티브 카운팅 (완료)
Phase 7C  ✅ 토큰 사용량 분석/예측 (완료) → 670 테스트 통과
Phase 8   ✅ Caveman 출력 압축 통합 (완료) → 671 테스트, v0.6.0
Phase 9   ✅ TUI/UX 대수선 (완료) → docs/test-results/phase-9-T.md
Phase 10  🔧 Interactive Provider Reliability (진행 중) → docs/plans/2026-06-02-phase-10-interactive-redesign.md, docs/test-results/phase-10-T.md
Phase 11  📋 v0.7.0 Multi-Agent Workflow Engine (계획 수립) → docs/plans/2026-06-03-v0.7.0-workflow-engine-redesign.md
```

### 테스트 Phase 공통 규칙

모든 테스트 Phase(Phase N-T)는 완료 시 `docs/test-results/phase-N-T.md`에 결과 문서를 작성한다.
문서에 포함할 필수 항목:

1. **요약** — 총 테스트 수, 통과/실패, 전체 커버리지, 실행 시간, 환경
2. **신규 테스트 상세** — 테스트 파일별 테스트 이름·설명 테이블
3. **커버리지 상세** — 모듈별 커버리지, 미커버 라인, 사유
4. **미커버 영역 분석** — 이유(Phase 의존, mock 한계 등)와 후속 조치
5. **발견된 이슈** — 테스트 작성 중 발견한 버그·개선점

---

## 참고

- **레포**: https://github.com/hongdangmoo49/Trinity
- **참고 아키텍처**: `docs/reference-architecture.md`
- **구현 계획**: `docs/plans/2026-06-02-prompt-compression.md`
- **Phase 9 설계**: `docs/plans/2026-06-02-tui-overhaul.md`

*작성일: 2026-06-01*
*갱신일: 2026-06-03 — v0.7.0 Multi-Agent Workflow Engine 재설계 계획 수립*
