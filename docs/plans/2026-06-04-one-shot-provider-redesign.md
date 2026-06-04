# 단발 Provider 호출 기반 재설계 분석

- 작성일: 2026-06-04
- 작업 브랜치: `codex/one-shot-provider-redesign`
- 범위: tmux 상시 세션 방식 제거, 라운드별 단발 호출, 중앙 요약/합의 에이전트, 사용자 PC 인증 재사용, Gemini CLI에서 Antigravity CLI 전환

## 결론

요구사항은 대체로 타당하다. Trinity의 라운드 기반 합의 구조는 provider별 상시 TUI 세션보다 단발 호출과 더 잘 맞는다. 각 라운드에서 동일한 공유 요약과 질의를 모든 에이전트에게 전달하면 provider 내부 세션 상태에 덜 의존하고, tmux pane 캡처/완료 감지/초기 auth 화면 문제도 줄일 수 있다.

단, 세 가지는 설계상 명확히 분리해야 한다.

1. 인증 재사용과 provider 상태 격리는 충돌한다. 현재처럼 `HOME`, `XDG_CONFIG_HOME`, `CODEX_HOME`류를 `.trinity/agents/<agent>/provider-state`로 돌리면 사용자의 기존 로그인 캐시와 OS keyring을 볼 수 없다. 기본값은 사용자 홈 인증을 그대로 쓰고, 격리는 작업 디렉터리/워크트리/Trinity 산출물 단위로 유지해야 한다.
2. Antigravity CLI는 공식 문서에서 TUI, keyring auth, resume, migration은 확인되지만 `claude -p` 또는 `codex exec`에 대응하는 비대화형 단발 호출 플래그는 문서상 확인되지 않았다. 구현 전 `agy --help` 또는 공식 문서 업데이트로 `--prompt`/출력 포맷 지원을 검증해야 한다.
3. OpenCode처럼 provider 호출과 local tool execution을 분리하는 구조는 장기적으로 유용하지만, 현재 Trinity가 목표로 하는 `claude -p`, `codex exec` 기반 CLI one-shot 인증 재사용과는 같은 방식이 아니다. CLI one-shot은 provider CLI 내부 도구/권한에 맡기는 `provider-managed` 실행이고, OpenCode식 구조는 API model이 tool call을 내면 Trinity가 로컬 도구를 실행하는 `trinity-managed` 실행이다.

## 현재 구조 분석

현재 `TrinityOrchestrator`는 interactive 모드에서 `TmuxSessionManager`를 만들고, `AgentFactory`가 각 provider를 `TmuxPane`과 `CompletionDetector`에 연결한다. 이후 `DeliberationProtocol._collect_opinions()`가 에이전트별 `send_and_wait()`를 병렬 실행한다.

현재 문제 지점:

- `src/trinity/workspace/managed_home.py`가 agent별 `provider-state`를 만들고 `HOME`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME`을 강제로 덮어쓴다.
- 이 때문에 Claude/Codex/Gemini가 사용자의 실제 `~/.claude`, `~/.codex`, OS keyring, Gemini/Antigravity 설정을 재사용하지 못한다.
- tmux mode는 provider별 TUI 화면을 캡처하고 prompt return, marker, idle detector로 완료를 추정한다. 이 방식은 초기 설정 화면, auth 화면, terminal rendering 변경에 취약하다.
- Claude는 이미 `PrintModeClaudeAgent`가 `claude -p --output-format json` 단발 호출을 지원한다.
- Codex/Gemini에도 print mode 경로가 있지만, Codex는 현재 문서화된 `codex exec`가 아니라 오래된 `codex -q` 형태를 사용한다.
- `Provider` enum은 `claude-code`, `codex`, `gemini-cli`만 갖고 있으며 `antigravity-cli`가 없다.

## Provider 문서 조사 요약

### Claude Code

공식 CLI reference는 `claude -p "query"`가 질의 후 종료하는 print mode이며, `--output-format`은 `text`, `json`, `stream-json`을 지원한다고 설명한다. 로컬 `claude --help`에서도 `-p, --print`, `--output-format`, `--input-format`, `--no-session-persistence`, `--append-system-prompt`가 확인됐다.

권장 호출:

```bash
claude -p --output-format json --append-system-prompt "<role>" "<round prompt>"
```

운영 선택지:

- 진행 표시가 필요하면 `--output-format stream-json`.
- 순수 단발 호출이면 `--no-session-persistence`.
- Claude 기본 도구 지침을 유지하려면 `--system-prompt`로 교체하기보다 `--append-system-prompt` 또는 prompt preamble을 사용한다.

### Codex CLI

Codex manual은 비대화형 실행을 `codex exec`로 문서화한다. `codex exec`는 최종 메시지를 stdout에 출력하고, `--json` 사용 시 JSONL event stream을 stdout에 낸다. `--ephemeral`은 세션 파일 저장을 피하며, 인증은 기본적으로 저장된 CLI 인증을 재사용한다. Codex auth cache는 `CODEX_HOME` 기본값인 `~/.codex` 아래 또는 OS credential store에 저장된다.

권장 호출:

```bash
codex exec --json --ephemeral --cd <project_dir> "<round prompt>"
```

운영 선택지:

- deliberation은 기본 `read-only` sandbox 또는 명시적 `--sandbox read-only`.
- 실행 단계는 별도 policy로 `workspace-write`.
- 현재 `CodexAgent._run_subprocess()`의 `codex -q`는 `codex exec` 기반으로 교체해야 한다.

### Gemini CLI

로컬 `gemini --help` 기준으로 `-p, --prompt`는 비대화형 headless mode를 지원한다. 그러나 Google은 2026-05-19 공식 블로그에서 Gemini CLI를 Antigravity CLI로 전환한다고 발표했고, 2026-06-18부터 Google AI Pro/Ultra 및 개인 무료 사용자 요청 제공이 중단된다고 밝혔다.

권장 방향:

- 신규 기본 provider에서 `gemini-cli`를 제거한다.
- 기존 설정 호환을 위해 `gemini-cli`는 deprecated provider로 유지하되, setup/readiness에서 Antigravity migration 안내를 표시한다.

### Antigravity CLI

공식 Antigravity CLI 문서에서 확인된 내용:

- 설치 binary는 `agy`.
- macOS/Linux 기본 설치 경로는 `~/.local/bin/agy`.
- 첫 실행은 `agy` TUI이며 color/rendering/workspace trust를 설정한다.
- 인증은 OS secure keyring을 먼저 사용하고, 저장 세션이 없으면 브라우저 또는 SSH OAuth URL flow로 진행한다.
- 설정 파일은 `~/.gemini/antigravity-cli/settings.json`.
- Gemini CLI migration은 `agy plugin import gemini`로 수행한다.
- conversation resume은 `/resume`, `agy --continue`, `agy --conversation <uuid>`가 문서화되어 있다.

공식 문서에서 아직 확인되지 않은 내용:

- `agy --prompt`, `agy -p`, `--output-format` 같은 단발 비대화형 호출.
- stdout machine-readable response format.
- auth 상태 확인용 `agy auth status` 같은 명령.

따라서 Antigravity provider는 구현 전 로컬 바이너리 검증이 필요하다. 현재 이 WSL 환경에는 `agy`/`antigravity` 명령이 설치되어 있지 않았다.

## 세션 직접 실행 vs 단발 호출 기능 차이

여기서 말하는 단발 호출은 OpenCode식 API/tool-call runtime이 아니라 provider CLI의 headless/non-interactive mode다. 즉 `claude -p`, `gemini -p`, `codex exec` 모두 provider CLI가 자체 도구와 권한 체계를 유지한다. Trinity가 직접 read/edit/write tool을 실행하는 구조가 아니다.

공통 차이:

| 항목 | 직접 세션 열기 | 단발 호출 |
| --- | --- | --- |
| 컨텍스트 | 같은 TUI 세션 안에서 자연스럽게 누적된다. | 기본은 한 번 실행 후 종료된다. 라운드마다 `shared.md` 요약과 질의를 다시 주입해야 한다. |
| 세션 재개 | resume/continue picker와 대화형 흐름에 적합하다. | provider별 resume 플래그나 session id를 쓸 수 있지만, Trinity 기본 흐름은 stateless 재주입이 더 안정적이다. |
| 권한 승인 | 사용자가 TUI에서 승인/거절하기 쉽다. | 승인 정책을 호출 전에 정해야 한다. 자동화에서는 read-only/plan 또는 명시적 workspace-write가 필요하다. |
| 출력 | 화면 repaint, status line, prompt echo, progress UI가 섞인다. | stdout/json/jsonl/stream-json 중심이라 artifact 저장과 parser 작성이 쉽다. |
| 파일 수정 | provider CLI 내부 도구로 가능하다. | provider CLI 내부 도구로 가능하지만 sandbox/permission mode를 명시해야 한다. |
| 자동화 안정성 | tmux capture와 완료 감지에 취약하다. | 프로세스 종료, exit code, stdout/stderr 기준으로 처리할 수 있다. |

### Claude Code

| 구분 | 직접 세션 `claude` | 단발 호출 `claude -p` |
| --- | --- | --- |
| 기본 동작 | interactive session을 시작한다. | prompt를 실행하고 종료한다. |
| 세션 유지 | `--continue`, `--resume`, `/resume` 흐름이 자연스럽다. | `-c -p`, `-r <session> -p` 조합은 가능하지만, Trinity에서는 canonical context 재주입을 기본으로 둔다. |
| 출력 형식 | TUI 중심이다. | `--output-format text/json/stream-json`을 지원한다. |
| 도구/권한 | 승인 UI와 장기 탐색에 적합하다. | `--tools`, `--allowedTools`, `--disallowedTools`, `--permission-mode`, `--add-dir`로 호출별 통제가 가능하다. |
| 자동화 옵션 | 사람 개입과 background/remote/IDE 흐름에 강하다. | `--no-session-persistence`, `--json-schema`, `--max-budget-usd`, `--bare`가 자동화에 유리하다. |
| 주의점 | 화면 캡처가 응답 추출을 어렵게 만든다. | print mode는 workspace trust dialog를 건너뛰므로 신뢰한 디렉터리에서만 써야 한다. |

Trinity 적용:

- deliberation: `claude -p --output-format json --permission-mode plan` 또는 도구 제한.
- execution: 파일 수정이 필요한 work package에서만 edit/bash 권한을 허용한다.
- 세션 기억보다 `shared.md` 요약과 prompt preamble을 신뢰한다.

### Codex CLI

| 구분 | 직접 세션 `codex` | 단발 호출 `codex exec` |
| --- | --- | --- |
| 기본 동작 | interactive TUI를 시작한다. | non-interactive agent run을 실행한다. |
| 세션 유지 | `codex resume`, `fork`, TUI thread 흐름에 적합하다. | `codex exec resume --last` 또는 session id로 이어갈 수 있다. |
| 출력 형식 | TUI 중심이다. | 기본 stdout은 최종 메시지이고 progress는 stderr다. `--json`은 JSONL event stream을 출력한다. |
| 도구/권한 | interactive approval과 sandbox 조정에 적합하다. | 기본은 read-only sandbox다. 수정하려면 `--sandbox workspace-write`가 필요하다. |
| 자동화 옵션 | 사람이 로컬에서 작업하기 좋다. | `--ephemeral`, `--output-schema`, `--output-last-message`, `--ignore-user-config`, `--ignore-rules`, `--cd`가 CI/Trinity에 유리하다. |
| 이벤트 관측 | TUI 화면에서 사람이 본다. | JSONL event에 command execution, file changes, MCP tool calls, web search, usage 등이 포함될 수 있어 parser 작성이 쉽다. |

Trinity 적용:

- deliberation: `codex exec --json --ephemeral --sandbox read-only --cd <repo> "<prompt>"`.
- execution: `codex exec --json --sandbox workspace-write --cd <repo> "<work package prompt>"`.
- Codex는 `--json` contract test를 우선 작성한다.

### Gemini CLI

| 구분 | 직접 세션 `gemini` | 단발 호출 `gemini -p/--prompt` |
| --- | --- | --- |
| 기본 동작 | interactive mode를 시작한다. | headless mode로 prompt를 실행한다. |
| 세션 유지 | `--resume`, session list/delete, interactive history에 적합하다. | `--resume latest/<id>`와 조합할 수 있지만, Trinity에서는 context 재주입을 기본으로 둔다. |
| 출력 형식 | TUI/REPL 중심이다. | `--output-format text/json/stream-json`을 지원한다. |
| 도구/권한 | approval prompt, extensions, MCP, skills, hooks를 interactive하게 다룬다. | `--approval-mode default/auto_edit/yolo/plan`, `--sandbox`, `--include-directories`로 호출별 정책을 정한다. |
| 하이브리드 | initial prompt 후 계속 대화하기 쉽다. | `--prompt-interactive`는 prompt 실행 후 interactive로 전환되므로 Trinity 기본 transport에는 맞지 않는다. |
| 리스크 | 기존 Gemini CLI 유지 여부와 전환 일정이 문제다. | headless 기능은 있으나 신규 기본 provider로는 Antigravity 전환 검증이 우선이다. |

Trinity 적용:

- deprecated 호환: `gemini -p "<prompt>" --output-format json --approval-mode plan`.
- execution 단계에서는 `auto_edit` 또는 명시 policy를 쓰되, 신규 기본 provider로 승격하지 않는다.
- Antigravity one-shot 지원이 확인되면 `gemini-cli`는 legacy provider로만 유지한다.

## Trinity 선택 기준

라운드 기반 합의와 중앙 synthesizer에는 단발 호출이 더 적합하다. 각 라운드마다 같은 canonical context를 모든 provider에 주입하면 provider 내부 세션 기억, TUI 화면 상태, auth/trust 초기 화면에 덜 의존한다.

권장 기본값:

```text
deliberation:
  claude -p ... --permission-mode plan
  codex exec ... --sandbox read-only
  gemini -p ... --approval-mode plan  # deprecated compatibility only

execution:
  claude -p ... with explicit edit/bash permission
  codex exec ... --sandbox workspace-write
  gemini -p ... --approval-mode auto_edit  # deprecated compatibility only
```

중요한 판단:

- 단발 호출은 기능 축소가 아니라 transport 안정화다. 파일 read/edit/write는 여전히 provider CLI 내부 도구로 가능하다.
- 단발 호출에서 장기 기억을 기대하지 않는다. Trinity가 `shared.md`, response artifacts, synthesis summary를 canonical memory로 관리한다.
- 엄격한 tool-level audit/control이 필요하면 provider-managed CLI 호출만으로는 부족하다. 그 경우 OpenCode식 `trinity-managed` API/tool-call runtime을 별도 구현해야 한다.

## 서브에이전트 병렬 실행 기준

서브에이전트를 병렬로 스폰하는 것은 가능하다. 다만 이번 redesign의 기본 경로가 `provider-managed` CLI 실행이라는 점 때문에, 병렬성은 작업 성격과 worktree 경계에 따라 제한해야 한다. `claude -p`, `codex exec`, `gemini -p`가 파일 read/edit/write를 수행하면 그 작업은 Trinity의 중앙 tool executor가 아니라 각 provider CLI 내부 도구가 수행한다. 따라서 같은 worktree에서 여러 provider CLI를 `workspace-write` 권한으로 동시에 실행하면 충돌, 중복 수정, 숨은 overwrite가 발생할 수 있다.

권장 분리:

| 작업 유형 | 병렬 허용 여부 | 기준 |
|---|---:|---|
| 문서/코드 구조 분석 | 허용 | read-only prompt와 sandbox를 사용한다. |
| provider별 CLI 옵션 조사 | 허용 | 로컬 파일 수정 권한 없이 실행한다. |
| 테스트 케이스 설계 | 허용 | 산출물은 artifact로 받고 최종 반영은 coordinator가 한다. |
| 서로 다른 파일/모듈 구현 | 조건부 허용 | 명확한 파일 소유권 또는 별도 git worktree가 필요하다. |
| 공유 orchestration/config 구현 | 순차 실행 | `agents/base.py`, provider config, workflow orchestration 같은 경계 파일은 coordinator가 병합한다. |
| 같은 worktree의 provider CLI execution | 금지에 가깝다 | `workspace-write` provider CLI를 동시에 여러 개 실행하지 않는다. |

권장 실행 모델:

```text
Coordinator
  - 전체 설계와 파일 소유권 관리
  - provider CLI write 권한 부여 여부 결정
  - 서브에이전트 산출물 검토
  - 최종 patch 적용과 전체 테스트 실행

Subagent A
  - Codex exec 전환 조사/구현 초안

Subagent B
  - Claude/Gemini one-shot 옵션 정리

Subagent C
  - ExecutionAuthority / ProviderTurnResult interface 설계

Subagent D
  - 테스트 케이스 작성
```

운영 규칙:

- read-only deliberation은 병렬 실행해도 된다.
- write 권한 execution은 기본적으로 순차 실행한다.
- 병렬 구현이 필요하면 provider별 또는 작업 단위별로 별도 git worktree를 만든다.
- 같은 파일을 둘 이상의 서브에이전트가 수정하지 않도록 coordinator가 파일 소유권을 먼저 할당한다.
- 서브에이전트는 직접 merge하지 않고 patch/artifact를 남기며, coordinator가 최종 적용한다.
- OpenCode식 `trinity-managed` local tool executor가 생기기 전까지는 Trinity가 모든 파일 I/O를 중앙에서 가로채지 못한다고 가정한다.

## OpenCode 구조 적용 판단

OpenCode는 provider CLI를 실행하지 않는다. TUI와 non-interactive `run` 모두 내부 session prompt를 만들고, 실제 LLM 호출은 AI SDK provider 객체를 통해 `streamText()`로 보낸다. 모델이 파일 읽기/수정을 요청하면 provider가 OS 파일을 직접 만지는 것이 아니라 tool call을 반환하고, OpenCode 프로세스가 로컬 `read`, `edit`, `write`, `apply_patch`, `shell` 도구를 실행한다.

이 구조에서 분리되는 것은 두 가지다.

- model transport: Anthropic/OpenAI/Google/OpenAI-compatible API 호출, streaming, provider options, auth header.
- local tool runtime: 파일 읽기/쓰기, shell, permission prompt, diff 기록, LSP diagnostics, tool result 반환.

Trinity에 바로 적용 가능한 부분은 "호출 계층과 실행 권한 계층을 분리해서 모델링하는 것"이다. 하지만 OpenCode식 구현을 그대로 쓰려면 Claude/Codex/Gemini CLI 인증 재사용이 아니라 API key/OAuth 기반 provider 인증과 Trinity 자체 tool executor가 필요하다. 따라서 이번 redesign에서는 구조를 다음처럼 나누는 것이 맞다.

```python
class ExecutionAuthority(str, Enum):
    PROVIDER_MANAGED = "provider-managed"  # claude/codex/agy CLI가 자체 도구와 권한으로 실행
    TRINITY_MANAGED = "trinity-managed"    # API model은 tool call만 내고 Trinity가 로컬 도구 실행
```

즉시 구현 범위:

- Claude/Codex one-shot invoker는 `PROVIDER_MANAGED`로 둔다.
- deliberation round는 기본적으로 "분석 전용/read-only" prompt와 provider sandbox flag를 사용한다.
- execution 단계에서 파일 수정을 허용할 때는 provider CLI의 permission/sandbox flag와 git worktree 경계로 통제한다.

장기 확장 범위:

- `TRINITY_MANAGED` runtime을 별도 추가한다.
- Anthropic/OpenAI/Gemini API provider는 tool schema를 받아 tool call event를 내고, Trinity `ToolExecutor`가 read/edit/write/shell을 로컬에서 실행한다.
- 이 경로에서는 provider HOME/auth cache가 아니라 API key/OAuth 저장소가 필요하므로 CLI one-shot 인증 재사용과 별도 설정으로 둔다.

중요한 설계 결론:

- `ProviderInvoker`는 단순히 "CLI subprocess를 실행하는 클래스"가 아니라 "모델 호출 결과를 Trinity가 이해하는 event/result로 정규화하는 계층"이어야 한다.
- `ProviderTurnResult`는 CLI one-shot의 최종 응답용으로 충분하지만, `TRINITY_MANAGED` runtime을 지원하려면 tool call/result를 표현하는 stream event 모델이 추가로 필요하다.
- CLI provider에서 local tool execution을 강제로 분리하려고 하면 안정성이 떨어진다. `claude -p`와 `codex exec`가 내부에서 도구를 실행하는 경우 Trinity는 stdout/event를 해석할 수 있을 뿐, tool call protocol을 표준화해서 가로채기 어렵다. 엄격한 tool 통제를 원하면 API tool-calling runtime을 별도로 구현해야 한다.

## 재설계 목표

1. tmux pane을 provider 호출의 기본 transport에서 제거한다.
2. 각 에이전트 호출은 `PromptRequest -> ProviderTurnResult` 단발 실행으로 통일한다.
3. 라운드 후 중앙 synthesizer가 모든 응답과 사용자 답변을 받아 요약, open questions, 합의 여부, 다음 라운드 질의를 생성한다.
4. `shared.md`는 provider 세션 메모리가 아니라 모든 에이전트에 다시 전달되는 canonical context가 된다.
5. 인증은 사용자의 실제 PC/WSL 설치와 auth cache를 재사용한다.
6. 작업 격리는 provider HOME 격리가 아니라 `cwd`, git worktree, sandbox/permission flag, Trinity artifact 디렉터리로 유지한다.
7. provider 호출과 local tool execution의 책임 경계를 명시한다. 이번 one-shot CLI 경로는 provider-managed 실행으로 시작하고, Trinity-managed local tool runtime은 별도 확장 지점으로 둔다.
8. 병렬 서브에이전트 실행은 read-only 분석과 분리된 worktree 구현에 우선 적용하고, 같은 worktree의 provider-managed write execution은 순차화한다.

## 제안 아키텍처

```text
TrinityOrchestrator
  RoundCoordinator
    ProviderInvokerFactory
      ClaudePrintInvoker
      CodexExecInvoker
      AntigravityInvoker
    ExecutionAuthorityPolicy
      provider-managed CLI path
      trinity-managed API/tool path
    ParallelExecutionPolicy
      file ownership
      worktree isolation
      write execution serialization
    LocalToolRuntime
      ToolRegistry
      PermissionGate
      ArtifactRecorder
    SynthesisAgent
      Provider-backed synthesizer
      Heuristic fallback
    SharedContextEngine
    WorkflowEngine
```

핵심 interface:

```python
@dataclass
class PromptRequest:
    agent_name: str
    provider: Provider
    role_prompt: str
    round_num: int
    prompt: str
    cwd: Path
    timeout_seconds: float
    env: dict[str, str]
    request_id: str

@dataclass
class ProviderTurnResult:
    agent_name: str
    content: str
    raw_output: str
    status: ResponseStatus
    elapsed_seconds: float
    usage: ContextUsage | None
    diagnostics: list[str]

class ProviderInvoker(Protocol):
    async def invoke(self, request: PromptRequest) -> ProviderTurnResult: ...
```

기존 `AgentWrapper.start()`, `is_alive()`, `graceful_shutdown()`은 상시 프로세스 기준이므로 one-shot 경로에서는 의미가 약하다. 새 구조에서는 provider lifecycle을 process lifecycle이 아니라 invocation lifecycle로 본다.

OpenCode식 확장까지 고려한 추가 interface:

```python
@dataclass
class ProviderToolCall:
    call_id: str
    tool_name: str
    arguments: dict[str, object]
    provider_metadata: dict[str, object]

@dataclass
class ProviderToolResult:
    call_id: str
    output: str
    metadata: dict[str, object]
    attachments: list[Path]

class LocalToolExecutor(Protocol):
    async def execute(self, call: ProviderToolCall) -> ProviderToolResult: ...
```

이 interface는 Phase 1의 Claude/Codex CLI one-shot 구현에 필수는 아니다. 하지만 이후 API-native provider를 붙일 때 `ProviderInvoker`를 다시 찢지 않기 위한 경계로 문서화한다.

## 라운드 흐름

1. 사용자 요청 또는 사용자 답변을 `RoundInput`으로 만든다.
2. `shared.md`의 현재 goal, 이전 round summary, decisions, open questions를 읽는다.
3. 모든 enabled agent에 동일한 `RoundPrompt`를 병렬 단발 호출한다.
4. 각 raw/clean 응답을 `.trinity/responses/round-XX/`에 저장한다.
5. 중앙 `SynthesisAgent`에 다음 입력을 전달한다.
   - 원 사용자 목표
   - 이전 synthesis summary
   - 이번 round agent 응답 목록
   - 사용자 답변 목록
   - 현재 decisions/open questions
6. `SynthesisAgent`가 `SynthesisResult`를 반환한다.
   - `consensus_reached`
   - `summary_for_shared_md`
   - `next_round_prompt`
   - `open_questions_for_user`
   - `decisions`
   - `recommended_blueprint`
7. `shared.md`에 round opinions 전체가 아니라 synthesis summary 중심으로 기록한다. 필요하면 raw artifact 링크를 남긴다.
8. 질문이 있으면 TUI가 사용자에게 묻고, 답변을 다음 round input에 포함한다.
9. 합의가 되었으면 WorkflowEngine이 work package 분해/실행 단계로 넘어간다.

## 중앙 에이전트 mount 시점

추천 시점은 "매 라운드 agent 응답 수집 직후"다.

장점:

- 모든 라운드에서 동일한 합의 판단 기준을 적용한다.
- 각 provider에게 다음 라운드에 전달할 요약과 질문을 안정적으로 생성한다.
- `shared.md`가 round별 장문 응답 누적으로 커지는 것을 막을 수 있다.

대안:

- 불일치 또는 질문 발생 시에만 mount: 비용은 줄지만, 합의 판단이 다시 heuristic에 의존한다.
- 라운드 전후 모두 mount: prompt 품질은 좋아지지만 호출 비용과 latency가 커진다.

이름은 `synthesizer`를 추천한다. `moderator`는 사용자와 대화하는 느낌이 강하고, `arbiter`는 의사결정 권한이 과하게 느껴진다. `synthesizer`는 요약/질문/합의 판단 역할을 정확히 드러낸다.

## 인증/설치 재설계

현재 기본값:

- agent별 managed home 생성
- `HOME`/XDG override
- provider별 새 auth 요구

변경 기본값:

- `ProviderStateMode.USER_HOME`를 기본으로 둔다.
- provider process에는 사용자의 실제 환경을 상속한다.
- `HOME`, `XDG_CONFIG_HOME`, `CODEX_HOME`은 기본적으로 덮어쓰지 않는다.
- 작업 격리는 `workspace_mode = inplace | git-worktree`와 provider sandbox flag로 유지한다.

선택 옵션:

```toml
[general]
provider_state_mode = "user-home"  # "user-home" | "isolated"

[agents.codex]
workspace_mode = "git-worktree"
```

provider readiness 변경:

- Claude: `command -v claude`, `claude --version`, 가능하면 `claude auth status`.
- Codex: `command -v codex`, `codex --version`, `codex doctor --json` 또는 auth cache/keyring 진단.
- Antigravity: `command -v agy`, `agy --version`, 공식 문서상 keyring silent auth이므로 실제 one-shot smoke test가 필요하다.

중요 보안 메모:

사용자 홈 auth를 그대로 쓰면 provider는 사용자의 실제 credentials와 일부 개인 설정을 읽을 수 있다. 이것은 사용자가 요구한 동작이지만, provider HOME 격리는 사라진다. 격리 목표는 credentials가 아니라 작업 파일/실행 권한/산출물 경계로 재정의해야 한다.

## Antigravity 전환 계획

Provider enum:

```python
class Provider(str, Enum):
    CLAUDE_CODE = "claude-code"
    CODEX = "codex"
    ANTIGRAVITY_CLI = "antigravity-cli"
    GEMINI_CLI = "gemini-cli"  # deprecated
```

기본 agent:

```toml
[agents.antigravity]
provider = "antigravity-cli"
cli_command = "agy"
enabled = false
```

마이그레이션:

- setup detector에서 `gemini` 대신 `agy`를 우선 탐지한다.
- 기존 `gemini-cli` config를 읽으면 deprecation warning을 표시한다.
- `trinity setup` 또는 `trinity doctor providers`에서 `agy plugin import gemini` 안내를 제공한다.
- Antigravity official docs에 단발 호출이 확인되기 전까지는 `antigravity-cli` provider를 experimental로 둔다.

## 구현 단계

### Phase 0 - Antigravity 검증

- `agy` 설치 여부 확인 로직 추가.
- 설치되어 있으면 `agy --help`, `agy --version` capture.
- `--prompt`/비대화형 출력/JSON 출력 지원 여부를 fixture로 기록.
- 공식 문서에 없는 플래그는 자동 사용하지 않고 experimental guard를 둔다.

### Phase 1 - One-shot 호출 계층

- `ProviderInvoker` interface 추가.
- Claude/Codex invoker부터 구현한다.
- `AgentWrapper` 기반 start/alive/shutdown 의존을 deliberation path에서 제거한다.
- fake CLI fixture로 timeout, stderr, JSONL parsing, auth-required parsing 테스트.

### Phase 1.5 - Provider/tool 권한 경계

- `ExecutionAuthority` 개념을 config/model에 추가한다.
- Claude/Codex/검증 전 Antigravity는 `provider-managed`로 분류한다.
- `ProviderTurnResult`에 `execution_authority`, `tool_activity_summary`, `artifact_paths` 필드를 추가할지 검토한다.
- local tool executor는 이번 phase에서 구현하지 않고 interface와 test seam만 둔다.
- deliberation prompt에는 "분석 전용, 파일 수정 금지"를 명시하고, 실행 phase prompt에서만 수정 권한을 허용한다.
- 병렬 서브에이전트 실행 정책을 추가한다. read-only 호출은 병렬 허용, 같은 worktree의 provider-managed write 호출은 순차 실행, 병렬 구현은 별도 git worktree 또는 명시적 파일 소유권이 있을 때만 허용한다.

### Phase 2 - 인증 상태 재사용

- `ManagedHome` 적용을 기본 비활성화한다.
- `provider_state_mode = "isolated"`일 때만 기존 managed home을 사용한다.
- `AgentLaunchContext.env_overrides`는 기본 `{}`로 둔다.
- readiness 문구에서 bootstrap을 기본 안내로 띄우지 않는다.

### Phase 3 - 중앙 synthesizer

- `SynthesisAgent`와 `SynthesisResult` schema 추가.
- 기본 mount 시점은 round 응답 수집 직후.
- provider-backed synthesizer 실패 시 기존 `StructuredConsensusSynthesizer`를 fallback으로 사용한다.
- `shared.md`에 `Round N Summary`, `Open Questions`, `Decisions`를 일관된 구조로 기록한다.

### Phase 4 - Antigravity provider

- `ANTIGRAVITY_CLI` provider 추가.
- `agy` official/verified one-shot command가 확인되면 invoker 구현.
- 확인 전에는 readiness에서 "installed but one-shot unsupported/unverified"로 표시한다.

### Phase 5 - tmux 호환 축소

- tmux interactive mode는 legacy/debug mode로 남긴다.
- 기본 `uv run trinity` deliberation은 one-shot transport를 사용한다.
- completion detector와 pane response cleaner는 legacy namespace로 이동하거나 deprecated 표시한다.

## 테스트 전략

- `tests/test_provider_invoker_claude.py`: command construction, JSON/stream parsing, auth error.
- `tests/test_provider_invoker_codex.py`: `codex exec --json` JSONL parsing, final message extraction, usage extraction.
- `tests/test_execution_authority.py`: CLI invoker가 `provider-managed`로 분류되고 deliberation prompt가 수정 금지 정책을 포함하는지 검증.
- `tests/test_parallel_execution_policy.py`: read-only 병렬 호출은 허용하고, 같은 worktree의 provider-managed write 호출은 거부/순차화하는지 검증.
- `tests/test_provider_state_mode.py`: user-home 기본값에서 `HOME`/XDG override가 없는지 검증.
- `tests/test_antigravity_detector.py`: `agy` 탐지, Gemini deprecation warning, migration guidance.
- `tests/test_round_synthesizer.py`: agent 응답 -> summary/questions/consensus 변환.
- `tests/test_deliberation_one_shot.py`: fake providers로 N라운드 합의와 사용자 질문 흐름 검증.

## 리스크와 대응

- Antigravity one-shot 미지원: 공식/로컬 검증 전까지 Antigravity provider를 experimental로 두고, Claude/Codex one-shot부터 전환한다.
- 사용자 홈 인증 공유: 사용자의 auth를 그대로 쓰는 대신 command sandbox, git worktree, permission flags를 강화한다.
- provider-managed 실행의 tool 투명성 한계: CLI 내부 도구 호출은 Trinity가 OpenCode처럼 세밀하게 가로채기 어렵다. 엄격한 파일 I/O 통제가 필요하면 API tool-calling 기반 `trinity-managed` runtime을 별도 구현한다.
- 병렬 provider-managed write 충돌: 같은 worktree에서 여러 provider CLI가 동시에 파일을 수정하지 않도록 write execution을 순차화하고, 병렬 구현은 별도 git worktree 또는 명시적 파일 소유권이 있을 때만 허용한다.
- 중앙 synthesizer 단일 실패점: provider-backed 호출 실패 시 heuristic fallback을 유지한다.
- context 증가: 모든 agent에게 전체 transcript가 아니라 synthesis summary와 필요한 raw artifact 링크만 전달한다.
- provider 출력 포맷 변경: JSON/JSONL parser는 provider별 fixture와 contract test를 둔다.

## 작업 착수 판단

바로 착수 가능한 작업:

- Claude/Codex one-shot invoker 전환.
- provider state 기본값을 user-home으로 바꾸는 작업.
- `synthesizer` schema와 round 후 mount 구조 추가.
- Gemini CLI deprecation warning과 `antigravity-cli` provider enum 추가.

착수 전 검증이 필요한 작업:

- Antigravity CLI의 단발 호출 플래그와 출력 포맷. 현재 환경에는 `agy`가 설치되어 있지 않고, 공식 markdown에는 비대화형 단발 호출이 문서화되어 있지 않다.

## 참고 출처

- Claude Code CLI reference: https://code.claude.com/docs/en/cli-usage
- Claude Code environment variables: https://code.claude.com/docs/en/env-vars
- Codex manual: https://developers.openai.com/codex/codex-manual.md
- Gemini CLI headless mode: https://google-gemini.github.io/gemini-cli/docs/cli/headless.html
- Gemini CLI reference: https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/cli-reference.md
- Antigravity CLI Getting Started: https://antigravity.google/assets/docs/cli/cli-getting-started.md
- Antigravity CLI Installation & Auth: https://antigravity.google/assets/docs/cli/cli-install.md
- Antigravity CLI Using AGY CLI: https://antigravity.google/assets/docs/cli/cli-using.md
- Antigravity CLI Reference: https://antigravity.google/assets/docs/cli/cli-reference.md
- Antigravity Gemini migration: https://antigravity.google/assets/docs/cli/gcli-migration.md
- Antigravity CLI conversations: https://antigravity.google/assets/docs/cli/cli-conversations.md
- Google Developers Blog - Transitioning Gemini CLI to Antigravity CLI: https://developers.googleblog.com/en/an-important-update-transitioning-gemini-cli-to-antigravity-cli/
