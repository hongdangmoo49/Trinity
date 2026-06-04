# 단발 Provider 호출 기반 재설계 분석

- 작성일: 2026-06-04
- 작업 브랜치: `codex/one-shot-provider-redesign`
- 범위: tmux 상시 세션 방식 제거, 라운드별 단발 호출, 중앙 요약/합의 에이전트, 사용자 PC 인증 재사용, Gemini CLI에서 Antigravity CLI 전환

## 결론

요구사항은 대체로 타당하다. Trinity의 라운드 기반 합의 구조는 provider별 상시 TUI 세션보다 단발 호출과 더 잘 맞는다. 각 라운드에서 동일한 공유 요약과 질의를 모든 에이전트에게 전달하면 provider 내부 세션 상태에 덜 의존하고, tmux pane 캡처/완료 감지/초기 auth 화면 문제도 줄일 수 있다.

단, 두 가지는 설계상 명확히 분리해야 한다.

1. 인증 재사용과 provider 상태 격리는 충돌한다. 현재처럼 `HOME`, `XDG_CONFIG_HOME`, `CODEX_HOME`류를 `.trinity/agents/<agent>/provider-state`로 돌리면 사용자의 기존 로그인 캐시와 OS keyring을 볼 수 없다. 기본값은 사용자 홈 인증을 그대로 쓰고, 격리는 작업 디렉터리/워크트리/Trinity 산출물 단위로 유지해야 한다.
2. Antigravity CLI는 공식 문서에서 TUI, keyring auth, resume, migration은 확인되지만 `claude -p` 또는 `codex exec`에 대응하는 비대화형 단발 호출 플래그는 문서상 확인되지 않았다. 구현 전 `agy --help` 또는 공식 문서 업데이트로 `--prompt`/출력 포맷 지원을 검증해야 한다.

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

## 재설계 목표

1. tmux pane을 provider 호출의 기본 transport에서 제거한다.
2. 각 에이전트 호출은 `PromptRequest -> ProviderTurnResult` 단발 실행으로 통일한다.
3. 라운드 후 중앙 synthesizer가 모든 응답과 사용자 답변을 받아 요약, open questions, 합의 여부, 다음 라운드 질의를 생성한다.
4. `shared.md`는 provider 세션 메모리가 아니라 모든 에이전트에 다시 전달되는 canonical context가 된다.
5. 인증은 사용자의 실제 PC/WSL 설치와 auth cache를 재사용한다.
6. 작업 격리는 provider HOME 격리가 아니라 `cwd`, git worktree, sandbox/permission flag, Trinity artifact 디렉터리로 유지한다.

## 제안 아키텍처

```text
TrinityOrchestrator
  RoundCoordinator
    ProviderInvokerFactory
      ClaudePrintInvoker
      CodexExecInvoker
      AntigravityInvoker
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
- `tests/test_provider_state_mode.py`: user-home 기본값에서 `HOME`/XDG override가 없는지 검증.
- `tests/test_antigravity_detector.py`: `agy` 탐지, Gemini deprecation warning, migration guidance.
- `tests/test_round_synthesizer.py`: agent 응답 -> summary/questions/consensus 변환.
- `tests/test_deliberation_one_shot.py`: fake providers로 N라운드 합의와 사용자 질문 흐름 검증.

## 리스크와 대응

- Antigravity one-shot 미지원: 공식/로컬 검증 전까지 Antigravity provider를 experimental로 두고, Claude/Codex one-shot부터 전환한다.
- 사용자 홈 인증 공유: 사용자의 auth를 그대로 쓰는 대신 command sandbox, git worktree, permission flags를 강화한다.
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
- Antigravity CLI Getting Started: https://antigravity.google/assets/docs/cli/cli-getting-started.md
- Antigravity CLI Installation & Auth: https://antigravity.google/assets/docs/cli/cli-install.md
- Antigravity CLI Using AGY CLI: https://antigravity.google/assets/docs/cli/cli-using.md
- Antigravity CLI Reference: https://antigravity.google/assets/docs/cli/cli-reference.md
- Antigravity Gemini migration: https://antigravity.google/assets/docs/cli/gcli-migration.md
- Antigravity CLI conversations: https://antigravity.google/assets/docs/cli/cli-conversations.md
- Google Developers Blog - Transitioning Gemini CLI to Antigravity CLI: https://developers.googleblog.com/en/an-important-update-transitioning-gemini-cli-to-antigravity-cli/

