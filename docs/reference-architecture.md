# Trinity Reference Architecture

> ChatDev v2.0 (DevAll) + CCB v6.2.9 에서 재사용 가능한 패턴·컴포넌트·설계 결정을 정리.
> Trinity가 직접 구현해야 할 영역과의 경계도 명시.

---

## 1. ChatDev — 가져올 것

### 1.1 Message 클래스 설계

**출처**: `entity/messages.py`

ChatDev의 Message는 역할·내용·출처·메타데이터를 하나의 객체로 관리한다.
Trinity의 토론 라운드에서 에이전트 간 의견을 주고받을 때 동일한 추상화가 필요하다.

```python
# ChatDev 원본 구조 (참고용)
class Message:
    role: MessageRole          # SYSTEM / USER / ASSISTANT / TOOL
    content: str | List[MessageBlock]  # 텍스트 또는 멀티모달 블록
    tool_calls: list | None
    metadata: dict             # source 노드, keep 여부 등

class MessageRole(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
```

**Trinity 적용 방안**:

```python
@dataclass
class DeliberationMessage:
    source: str              # "claude" | "codex" | "gemini" | "user"
    target: str              # "all" | 특정 에이전트명
    round: int               # 토론 라운드 번호
    role: str                # "opinion" | "counter" | "agreement" | "consensus"
    content: str             # 의견 본문
    timestamp: float
    metadata: dict           # token_count, context_window 등
```

---

### 1.2 keep_message — 원본 프롬프트 영구 유지

**출처**: `runtime/edge/conditions/base.py`, `ChatDev_v1.yaml`

ChatDev는 사용자의 원본 요청을 `keep: true`로 마킹하여,
context 초기화나 세션 교체 후에도 원본이 유지되도록 한다.

```yaml
# ChatDev_v1.yaml — 모든 downstream 에이전트가 원본을 잃지 않음
- source: USER
  target: "Chief Executive Officer"
  keep_message: true
```

**Trinity 적용 방안**:

- 세션 교체 시 `shared.md`의 `## 현재 목표` 섹션을 `keep` 마킹
- 새 세션의 첫 프롬프트에 반드시 포함
- 토론 라운드가 아무리 길어져도 원래 사용자 요청이 안 보이면 안 됨

```python
class SharedContext:
    pinned_sections: list[str] = ["현재 목표", "합의된 결론"]

    def get_context_for_new_session(self) -> str:
        """세션 교체 시 호출 — pinned 섹션은 항상 포함"""
        return self.render(include_pinned=True, max_recent_rounds=3)
```

---

### 1.3 context_window — 컨텍스트 크기 관리

**출처**: `runtime/node/executor/base.py`

```python
# ChatDev의 context_window 설정
context_window = 0     # 실행 후 전체 클리어 (keep 마킹만 남김)
context_window = -1    # 무제한 유지
context_window = N     # 최근 N개 메시지만 유지 + keep 마킹된 것
```

**Trinity 적용 방안**:

- 각 에이전트에 `context_budget` 설정 (예: 120K 토큰)
- 60% 도달(72K) 시 세션 교체 트리거
- 교체 시 `context_window = 0` 처럼 과거를 클리어하되 `keep` 섹션만 유지
- 최근 N개 라운드의 요약은 새 세션에 주입

| 설정값 | Trinity 의미 |
|--------|-------------|
| `keep_sections` | 세션 교체 후에도 유지할 shared.md 섹션 |
| `recent_rounds` | 새 세션에 가져갈 최근 토론 라운드 수 |
| `summary_budget` | 세션 요약에 할당할 최대 토큰 |

---

### 1.4 Loop Counter + 조건부 종료

**출처**: `entity/configs/node/loop_counter.py`, `runtime/edge/conditions/`

```yaml
# ChatDev — Code Review 루프 (최대 10회, "<INFO> Finished" 시 조기 종료)
- type: loop_counter
  config:
    max_iterations: 10

- condition:
    type: keyword
    config:
      any: ["<INFO> Finished"]
```

**Trinity 적용 방안**:

토론 라운드에 동일한 패턴 적용:

```python
class DeliberationLoop:
    max_rounds: int = 5
    consensus_keywords: list[str] = ["동의", "agree", "합의", "consensus"]

    def should_continue(self, round_outputs: dict) -> bool:
        """합의 도달 또는 최대 라운드 초과 시 종료"""
        if self.current_round >= self.max_rounds:
            return False
        if self.detect_consensus(round_outputs):
            return False
        return True

    def detect_consensus(self, outputs: dict) -> bool:
        """
        판정 방법 (선택):
        1. 키워드 기반 (빠르지만 부정확)
        2. LLM 판정 (정확하지만 비용 발생)
        3. 정형 출력 파싱 (에이전트에게 포맷 강제)
        """
        ...
```

---

### 1.5 MajorityVote — 다수결 합의

**출처**: `workflow/runtime/execution_strategy.py` → `MajorityVoteStrategy`

```python
# ChatDev
class MajorityVoteStrategy:
    def run(self) -> str:
        results = parallel_execute(all_nodes)
        majority_output, count = Counter(results).most_common(1)[0]
        return majority_output
```

**Trinity 적용 방안**:

3개 에이전트가 각자 최종안을 제출한 후 다수결로 결정:

```python
class ConsensusEngine:
    def resolve(self, proposals: dict[str, str]) -> str:
        """
        proposals = {
            "claude": "JWT + 세션 하이브리드",
            "codex": "JWT + 세션 하이브리드",
            "gemini": "순수 OAuth 2.0"
        }
        → "JWT + 세션 하이브리드" (2/3 다수)
        """
        # 방법 1: 키워드 유사도 기반 클러스터링
        # 방법 2: 임베딩 코사인 유사도
        # 방법 3: 별도 LLM 호출로 "이 의견들이 같은 건가?" 판정
        ...
```

---

### 1.6 AgentRetryConfig — API 재시도/복구

**출처**: `entity/configs/node/agent.py`

```python
# ChatDev
@dataclass
class AgentRetryConfig:
    max_attempts: int = 3
    backoff_factor: float = 1.0        # 지수 백오프
    retryable_status_codes: list = [408, 429, 500, 501, 502, 503, 504]
    retryable_exceptions: list = [RateLimitError, TimeoutError]
```

**Trinity 적용 방안**:

CLI 기반이므로 API 에러 코드 대신 CLI 종료 코드와 출력 기반:

```python
@dataclass
class RetryConfig:
    max_attempts: int = 3
    backoff_seconds: float = 5.0
    retryable_exit_codes: list[int] = [1, 137]  # 일반 에러, OOM kill
    retryable_output_patterns: list[str] = [
        "rate limit",
        "context window exceeded",
        "connection reset",
        "timeout",
    ]
```

---

### 1.7 ParallelExecutor — 병렬 실행

**출처**: `workflow/executor/parallel_executor.py`

ChatDev는 같은 topological layer의 노드를 스레드로 병렬 실행한다.
Trinity의 토론 라운드에서도 3개 에이전트에게 동시에 프롬프트를 보내고
각각의 응답을 병렬로 기다리는 패턴이 동일하다.

```python
# ChatDev 패턴
class ParallelExecutor:
    def execute(self, nodes: list[Node]) -> list[Result]:
        with ThreadPoolExecutor() as pool:
            futures = {pool.submit(n.execute): n for n in nodes}
            return [f.result() for f in as_completed(futures)]
```

**Trinity 적용**:

```python
# 3개 에이전트에게 동시에 프롬프트 주입 → 병렬로 완료 대기
async def run_round(self, prompt: str) -> dict:
    tasks = {
        name: self._send_and_wait(agent, prompt)
        for name, agent in self.agents.items()
    }
    return await asyncio.gather(*tasks.values())
```

---

## 2. CCB — 가져올 것

### 2.1 Provider별 완료 감지 (Completion Detection)

**출처**: `lib/providers/*/` (lib/은 공개 안 되지만 test/와 plans/로 유추 가능)

CCB는 각 Provider(Claude, Codex, Gemini)마다 서로 다른 방식으로
에이전트의 작업 완료를 감지한다. 이게 가장 구현하기 까다로운 부분이며,
CCB가 이미 검증한 패턴을 참고할 수 있다.

| Provider | CCB의 감지 방식 | Trinity 적용 |
|----------|----------------|-------------|
| **Claude Code** | Stop-hook의 `CCB_REQ_ID` 이벤트, 프롬프트 `$` 재등장 | Claude hook 설정 또는 pane 출력에서 프롬프트 대기 패턴 감지 |
| **Codex** | 세션 파일(JSON) 폴링, `usage.total_tokens` 읽기 | 세션 파일에서 완료 상태 폴링 |
| **Gemini** | 출력 유휴 타임아웃(15초), `CCB_DONE` 마커, `AfterAgent` hook | idle 타이머 + 선택적 마커 주입 |

**Trinity 구현 가이드**:

```python
class CompletionDetector(ABC):
    """Provider별 완료 감지 기반 클래스"""

    @abstractmethod
    async def wait_for_completion(self, agent: AgentWrapper) -> str:
        """에이전트가 출력을 끝낼 때까지 대기 후 응답 반환"""
        ...


class ClaudeCompletionDetector(CompletionDetector):
    """
    방법 1 (권장): Claude hook 활용
      - ~/.claude/settings.json에 Stop hook 등록
      - hook이 파일에 완료 신호를 기록
      - detector가 파일을 watch

    방법 2 (fallback): pane 출력 폴링
      - capture-pane으로 출력 변화 감지
      - Claude 프롬프트($)가 다시 나타나면 완료로 판단
    """
    prompt_pattern: str = r"[$>]\s*$"  # Claude CLI 프롬프트 패턴
    idle_timeout: float = 10.0         # 10초 무출력 = 완료


class CodexCompletionDetector(CompletionDetector):
    """
    Codex 세션 파일 폴링:
      - ~/.codex/sessions/ 에서 최신 JSON 파일 탐색
      - 세션 상태 필드 확인
      - usage 필드에서 토큰 카운트 추출 (context limit 감지에도 사용)
    """
    session_dir: Path = Path.home() / ".codex" / "sessions"


class GeminiCompletionDetector(CompletionDetector):
    """
    Gemini는 가장 불안정한 편:
      - idle 타임아웃을 길게 (15~20초)
      - 마커 주입: 프롬프트에 "완료 후 [DONE] 출력" 지시
      - fallback: 타임아웃 (120초)
    """
    idle_timeout: float = 20.0
    marker: str = "[DONE]"
    hard_timeout: float = 120.0
```

---

### 2.2 Context 사용량 추적

**출처**: `plans/` 디렉토리의 provider state storage boundary 문서들

CCB는 Provider별로 context 사용량을 추적하여 heartbeat 타임아웃과 연동한다.
Trinity는 이걸 **세션 교체 트리거**로 사용한다.

| Provider | 토큰 카운트 획득 방법 |
|----------|---------------------|
| **Claude Code** | Stop-hook 출력의 `usage` 필드, 또는 `claude --output-format json` 파싱 |
| **Codex** | 세션 JSON의 `usage.total_tokens` / `usage.prompt_tokens` |
| **Gemini** | CLI 출력에서 `Token count: N` 정규식 매칭 (불안정) |

**Trinity 구현**:

```python
@dataclass
class ContextUsage:
    used: int
    total: int

    @property
    def ratio(self) -> float:
        return self.used / self.total if self.total > 0 else 0.0

    @property
    def should_rotate(self) -> bool:
        return self.ratio >= 0.60


class ContextMonitor:
    THRESHOLD = 0.60
    # Provider별 context window 크기 (2026년 기준, 변경 가능)
    DEFAULT_LIMITS = {
        "claude": 200_000,    # Claude 200K
        "codex": 128_000,     # GPT-5 128K
        "gemini": 1_000_000,  # Gemini 1M
    }

    def get_usage(self, agent_name: str) -> ContextUsage:
        provider = self.agents[agent_name].provider
        detector = self.detectors[provider]
        return detector.get_token_count()
```

---

### 2.3 세션 교체 (Session Rotation)

**출처**: CCB의 restore/restart 메커니즘 (plans/ 참고)

CCB에는 자동 세션 교체가 없지만, 수동 restore가 있다.
Trinity는 이걸 **자동화**하는 것이 핵심 차별점이다.

```python
class SessionRotator:
    """
    Context limit 도달 시:
    1. 현재 에이전트에게 요약 요청
    2. shared.md 업데이트
    3. 현재 세션 종료
    4. 새 세션 시작 (shared.md + 요약 주입)
    """

    SUMMARY_PROMPT = """
    [시스템] 세션 교체를 위해 작업을 요약해주세요.

    다음 정보를 간결하게 정리:
    1. 완료한 작업
    2. 진행 중인 작업 (현재 상태)
    3. 다음에 해야 할 작업
    4. 중요한 결정 사항과 그 이유

    출력 형식:
    ## 완료
    - ...
    ## 진행 중
    - ...
    ## 다음 단계
    - ...
    ## 결정 사항
    - ...
    """

    CONTINUATION_PROMPT = """
    [시스템] 이전 세션에서 이어서 작업합니다.

    ## 공유 컨텍스트
    {shared_context}

    ## 이전 세션 요약
    {session_summary}

    ## 당신의 역할
    {agent_role}

    위 컨텍스트를 숙지하고 작업을 계속 진행하세요.
    """

    async def rotate(self, agent_name: str):
        agent = self.agents[agent_name]

        # 1. 요약 요청
        summary = await agent.send_and_wait(self.SUMMARY_PROMPT)

        # 2. shared.md 업데이트
        self.shared_context.append_session_summary(agent_name, summary)

        # 3. 현재 세션 종료
        await agent.graceful_shutdown()

        # 4. 새 세션 시작
        prompt = self.CONTINUATION_PROMPT.format(
            shared_context=self.shared_context.read(),
            session_summary=summary,
            agent_role=agent.role_description,
        )
        await agent.start(prompt=prompt)

        # 5. 다른 에이전트에게 알림
        self.broadcast(f"[{agent_name} 세션이 교체되었습니다. 요약이 shared context에 반영됨.]")
```

---

### 2.4 Agent 격리 (Managed Home)

**출처**: `lib/providers/*/`, `plans/session-isolation-contracts/`

CCB는 각 에이전트를 독립적인 홈 디렉토리에서 실행하여
Provider 설정, 세션, 인증이 서로 오염되지 않게 한다.

```
.ccb/agents/
├── main/
│   └── provider-state/
│       └── claude/home/     ← Claude 격리 홈
├── worker/
│   └── provider-state/
│       └── codex/home/      ← Codex 격리 홈
└── inspiration/
    └── provider-state/
        └── gemini/home/     ← Gemini 격리 홈
```

**Trinity 적용**:

```
.trinity/
├── trinity.config
├── shared.md                ← 공유 컨텍스트
├── agents/
│   ├── claude/
│   │   ├── role.md          ← 역할 정의
│   │   └── provider-state/  ← 격리된 Claude 홈
│   ├── codex/
│   │   ├── role.md
│   │   └── provider-state/  ← 격리된 Codex 홈
│   └── gemini/
│       ├── role.md
│       └── provider-state/  ← 격리된 Gemini 홈
├── workspace/               ← worktree (필요 시)
│   └── codex/               ← Codex 전용 git worktree
├── history/                 ← 세션 히스토록 요약
│   ├── session-001.md
│   └── session-002.md
└── logs/                    ← 실행 로그
```

---

### 2.5 Workspace 격리 모드

**출처**: CCB compact config의 `(worktree)` 문법

| 모드 | 설명 | 용도 |
|------|------|------|
| `inplace` | 프로젝트 루트에서 직접 작업 | 리뷰어, 코디네이터 |
| `git-worktree` | `.trinity/workspace/<name>/`에 격리 | 구현 에이전트 (충돌 방지) |

**Trinity config 예시**:

```toml
# trinity.config
agents = "claude:inplace, codex:worktree, gemini:inplace"

[agents.codex]
workspace_mode = "git-worktree"
branch_template = "trinity/{agent_name}"
```

---

### 2.6 tmux 기반 에이전트 제어

**출처**: CCB 전체 아키텍처의 기반

CCB가 검증한 tmux 제어 패턴:

```bash
# 에이전트에게 입력 주입
tmux send-keys -t <pane_id> "프롬프트 텍스트" Enter

# 긴 텍스트는 heredoc으로
tmux send-keys -t <pane_id> "cat << 'EOF'
...긴 프롬프트...
EOF
" Enter

# 에이전트 출력 읽기
tmux capture-pane -t <pane_id> -p -S -100  # 최근 100줄

# 세션/pane 관리
tmux new-session -d -s trinity
tmux split-window -h -t trinity
tmux attach -t trinity
```

**Trinity에서 주의할 점** (CCB가 겪은 문제들):

| 문제 | CCB의 해결 | Trinity 적용 |
|------|-----------|-------------|
| WSL 마운트 드라이브에서 Unix socket 불안정 | 런타임 상태를 로컬 Linux 경로로 이동 | `.trinity/`는 `/home/user/` 아래에 |
| tmux 레이아웃 깨짐 | `tmux -f /dev/null`로 유저 설정 무시 | 동일하게 적용 |
| pane crash 후 복구 | heartbeat + respawn | 세션 교체 메커니즘으로 통합 |
| send-keys 특수문자 이스케이프 | heredoc 활용 | 동일 |

---

## 3. Trinity만의 고유 영역 (새로 구현)

위 두 프로젝트에서 가져올 수 없는, Trinity가 직접 만들어야 할 것들.

### 3.1 공유 컨텍스트 엔진

ChatDev는 메시지 패싱, CCB는 파일 전달.
Trinity는 **실시간 공유 문서**를 모든 에이전트가 동시에 읽고 쓰는 모델.

```python
class SharedContextEngine:
    """
    shared.md를 실시간으로 관리.
    모든 에이전트가 같은 파일을 읽고, 변경 시 서로에게 알림.
    """
    path: Path                    # .trinity/shared.md
    watchers: dict[str, float]    # agent_name → last_read_timestamp

    def read(self) -> str: ...
    def write_section(self, section: str, content: str): ...
    def append_opinion(self, agent: str, round: int, content: str): ...
    def update_task_status(self, agent: str, status: str): ...
    def on_change(self, callback): ...  # file watcher
```

### 3.2 라운드 기반 토론 프로토콜

ChatDev는 파이프라인, CCB는 비동기 메시지.
Trinity는 **동기적 토론 라운드**:

```
Round 0: [ALL → "의견 제시"]        → 병렬 수집
Round 1: [ALL → "타 의견에 대한 반론/동의"] → 병렬 수집
Round N: [합의 판정] 또는 [계속]
최종:   [분담표 생성] → [각자 실행]
```

### 3.3 동적 분담

ChatDev는 YAML로 정적 분담.
Trinity는 **에이전트가 토론 후 스스로 분담**을 결정:

```python
class TaskDistributor:
    def distribute(self, consensus: str, agents: dict) -> dict:
        """
        합의된 내용을 바탕으로 각 에이전트에게 태스크 할당.
        에이전트의 강점에 따라 자동 매칭:
          - Claude: 아키텍처, 복잡한 로직, 코드리뷰
          - Codex: 대량 구현, 빠른 프로토타이핑
          - Gemini: 테스트, 문서, 대안 탐색
        """
        ...
```

### 3.4 에이전트 간 헬스체크

CCB는 daemon→agent 단방향 heartbeat.
Trinity는 **에이전트 간 양방향** 헬스체크:

```python
class HealthChecker:
    async def check_agent(self, name: str) -> AgentHealth:
        """
        - 응답 가능한가? (pane이 살아있는가)
        - context 사용량은? (60% 이상인가)
        - 진행 상태는? (멈춘 건 아닌가)
        """
        ...

    async def agent_ping(self, from_agent: str, to_agent: str) -> bool:
        """에이전트 A가 에이전트 B에게 직접 핑"""
        ...
```

---

## 4. 종합 — 컴포넌트 매핑

| Trinity 컴포넌트 | ChatDev에서 | CCB에서 | 새로 구현 |
|------------------|:-----------:|:-------:|:---------:|
| Message 클래스 | ✅ 가져옴 | — | — |
| keep_message (원본 유지) | ✅ 가져옴 | — | — |
| context_window 관리 | ✅ 가져옴 | — | 🔧 세션 교체 자동화 |
| Loop Counter (토론 라운드) | ✅ 가져옴 | — | 🔧 합의 판정 로직 |
| MajorityVote | ✅ 가져옴 | — | — |
| AgentRetryConfig | ✅ 가져옴 | — | 🔧 CLI 에러 기반으로 변형 |
| ParallelExecutor | ✅ 가져옴 | — | — |
| Provider별 완료 감지 | — | ✅ 참고 | 🔧 직접 구현 |
| Context 사용량 추적 | — | ✅ 참고 | 🔧 자동 회전 트리거 |
| 세션 교체 메커니즘 | — | ✅ restore 참고 | 🔧 자동화 (핵심) |
| Agent 격리 (Managed Home) | — | ✅ 가져옴 | — |
| Workspace 격리 (worktree) | — | ✅ 가져옴 | — |
| tmux 제어 패턴 | — | ✅ 가져옴 | — |
| **공유 컨텍스트 엔진** | — | — | ✅ **신규** |
| **라운드 기반 토론 프로토콜** | — | — | ✅ **신규** |
| **동적 분담** | — | — | ✅ **신규** |
| **에이전트 간 헬스체크** | — | — | ✅ **신규** |

---

## 5. 참고 자료

### ChatDev
- Repo: https://github.com/OpenBMB/ChatDev (branch: chatdev1.0)
- Paper: arXiv:2307.07924 (Communicative Agents for Software Development)
- DevAll 2.0 Paper: arXiv:2406.07155 (MacNet — DAG topology)
- Puppeteer: arXiv:2505.19591 (NeurIPS 2025 — learnable orchestrator)

### CCB
- Repo: https://github.com/SeemSeam/claude_codex_bridge (v6.2.9)
- 핵심 참고 디렉토리:
  - `plans/` — 30+ 설계 문서 (mailbox kernel, session isolation 등)
  - `archive/docs/` — v2 아키텍처 스펙 (154K)
  - `mcp/` — MCP 서버 구현 참고
  - `test/` — 200+ 테스트 (provider별 완료 감지 패턴)

---

*문서 생성일: 2026-06-01*
*Trinity v0.1.0 — 프로젝트 초기 설계 단계*
