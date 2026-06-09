# Provider Session and Model Context Reliability Design

- 작성일: 2026-06-09
- 작업 브랜치: `feature/provider-session-model-context-design`
- 상태: design draft
- 관련 문서:
  - `docs/plans/2026-06-04-one-shot-provider-redesign.md`
  - `docs/plans/2026-06-04-model-backed-synthesis.md`
  - `docs/plans/2026-06-07-execution-resume-recovery.md`
  - OpenAI Codex CLI reference: https://developers.openai.com/codex/cli/reference
  - Antigravity CLI conversations: https://antigravity.google/docs/cli-conversations
  - Antigravity CLI using guide: https://www.antigravity.google/docs/cli-using

## 목적

이번 작업의 목적은 Trinity가 provider CLI를 one-shot으로 호출하더라도 다음 정보를 신뢰 가능한 상태로 관리하게 만드는 것이다.

1. 각 agent가 실제로 사용한 모델명
2. 각 모델의 context window와 budget 산정 근거
3. 각 provider native session/thread/conversation id
4. Trinity workflow id와 provider session id의 안정적인 매핑
5. 같은 Trinity 세션 안에서 이어지는 agent 호출의 provider-native continuation

현재 Trinity는 `wf-...` workflow id와 `round-*`, `exec-*`, `review-*`, `synthesis-*` request id를 자체 생성해서 artifact를 묶는다. 하지만 provider CLI가 실제로 반환하거나 로그에 남기는 `session_id`, `thread_id`, `conversation_id`는 구조적으로 저장하지 않는다. 그 결과 Claude, Codex, Antigravity의 실제 대화 세션 지속성과 모델/컨텍스트 관측값을 UI와 workflow가 신뢰하기 어렵다.

## 현재 검증 결과

2026-06-09 WSL `/home/user/workspace/Trinity`에서 실제 CLI 호출과 로컬 설정을 확인했다.

| Agent | Trinity config model | 실제 확인 모델 | 확인 근거 | 현재 budget 신뢰도 |
| --- | --- | --- | --- | --- |
| `claude` | `opus[1m]` | `GLM-5.1[1m]` | `claude --model 'opus[1m]' -p --output-format json ...` 응답의 `modelUsage` | 높음. 응답에 `contextWindow: 1000000` 포함 |
| `codex` | `default` | `gpt-5.5` | Trinity가 `--model`을 생략하고, `~/.codex/config.toml`에 `model = "gpt-5.5"` | 중간-높음. `~/.codex/models_cache.json`에 `context_window: 272000` |
| `antigravity` | `default` | `Gemini 3.5 Flash (Medium)` | `agy --print ...` 실행 후 CLI 로그에 `Propagating selected model override ...` | 중간. 모델 label은 확인, context window는 CLI가 노출하지 않음 |

추가 확인:

- Claude print JSON은 `session_id`를 반환한다.
- Codex JSONL은 `thread.started` 이벤트에서 `thread_id`를 반환한다.
- Antigravity print mode 로그는 `conversation=<uuid>`를 기록한다.
- Trinity는 위 provider-native id를 현재 workflow/session state에 저장하지 않는다.

## 문제 정의

### 1. Config model과 actual model이 다르다

`AgentSpec.model`은 사용자가 요청한 값 또는 provider CLI에 넘길 값이다. 실제 serving model과 같다는 보장이 없다.

예시:

```text
Trinity config: claude model = opus[1m]
Claude JSON:    modelUsage.GLM-5.1[1m].contextWindow = 1000000
```

따라서 UI와 budget 계산은 `configured_model`과 `actual_model`을 분리해야 한다.

### 2. Context budget source가 불명확하다

현재 `context_budget`은 config 또는 provider 기본값으로 잡힌다. 하지만 실제 확인 결과 Codex는 `gpt-5.5`의 local cache context window가 `272000`인데 Trinity config는 `128000`이다. Antigravity는 `1000000`으로 설정되어 있지만 검증 근거가 없다.

Budget 값은 숫자만 표시하면 안 되고 source와 confidence를 같이 가져야 한다.

### 3. One-shot이 완전 stateless로 동작한다

현재 Claude 호출은 매번 아래 형태다.

```bash
claude --model 'opus[1m]' -p --output-format json ... '<prompt>'
```

`-c`, `--continue`, `--resume`, `--session-id`를 사용하지 않는다. 그래서 Claude native session 관점에서는 매번 새 print call이다. Trinity가 shared context를 prompt에 재주입해서 연속성을 흉내 내고 있지만 provider-native conversation memory는 이어지지 않는다.

### 4. `-c`는 automation에 위험하다

Claude의 `-c`는 현재 디렉토리에서 가장 최근 대화를 계속한다. 사용자나 다른 Trinity workflow가 같은 디렉토리에서 Claude를 실행했다면 엉뚱한 대화를 이어갈 수 있다.

Trinity는 `claude -c -p`를 기본으로 쓰면 안 된다. 첫 호출에서 얻은 `session_id`를 저장하고, 이후 호출은 명시적인 `--resume <session_id>`를 사용해야 한다.

### 5. Codex `--ephemeral`은 session continuity와 충돌한다

현재 Codex 호출은 `codex exec --json --ephemeral ...`이다. `--ephemeral`은 session file persistence를 피하는 옵션이므로, provider-native resume을 설계하려면 continuity mode에서는 제거해야 한다.

OpenAI Codex CLI reference 기준으로 `codex exec`는 비대화형 실행에 맞고 `--json`, `--cd`, `--sandbox`, `--model`, `--ephemeral`을 지원한다. 또한 `PROMPT` 자리에 `-`를 넣으면 stdin으로 prompt를 읽을 수 있으므로, Trinity는 긴 prompt를 argv 마지막 인자로 붙이지 말고 stdin으로 전달하는 방식을 기본으로 잡는 것이 안전하다.

Codex는 `codex exec resume [SESSION_ID] [PROMPT]`를 지원한다. `--last`와 `--all`도 있지만 자동화에서는 다른 workflow의 최근 session과 섞일 수 있으므로 사용하지 않는다. Trinity는 반드시 JSONL의 `thread.started.thread_id`를 저장하고, 저장된 명시적 `thread_id`로만 resume해야 한다.

공식 reference는 `--cd`, `--sandbox`를 global flag로 설명하지만, local `codex exec resume --help`의 resume option 목록에는 일반 `codex exec`만큼 명확하게 드러나지 않는다. 따라서 초기 구현에서는 Codex resume이 cwd/sandbox를 어떻게 적용하거나 상속하는지 contract test를 먼저 작성해야 한다.

### 6. Antigravity는 stdout contract가 부족하다

Antigravity는 `agy --print` stdout에 model/conversation metadata를 machine-readable하게 주지 않는다. 하지만 `--log-file` 옵션이 있고 로그에 `conversation=<uuid>`와 selected model label이 남는다. Trinity는 Antigravity 호출마다 전용 log file을 지정하고 그 로그를 parse해야 race를 줄일 수 있다.

Antigravity도 Codex와 같은 개념으로 provider-native continuation을 사용할 수 있다. 다만 Codex가 JSONL `thread.started.thread_id`를 stdout으로 주는 것과 달리, Antigravity는 stdout이 plain text라서 `provider_conversation_id`를 로그에서 관측해야 한다.

공식 conversation 문서에는 `agy --continue`와 `agy --conversation <uuid>`가 있다. 자동화에서는 `--continue`가 "현재 workspace의 가장 최근 conversation"을 고르므로 사용하지 않는다. Trinity는 저장된 명시적 `--conversation <uuid>`만 사용한다.

현재 `agy --help`에는 `--print`, `--print-timeout`, `--sandbox`, `--model`, `--log-file`, `--conversation`, `--continue`, `--dangerously-skip-permissions`가 확인된다. 반면 `agy --print -`처럼 stdin prompt를 받는 계약은 문서와 help에서 확인되지 않았다. 따라서 Antigravity는 Codex처럼 prompt stdin 전달을 기본으로 하지 않고, 별도 smoke test가 통과하기 전까지 prompt를 positional argv로 전달한다.

## 설계 원칙

1. Runtime observed metadata를 최우선으로 신뢰한다.
2. Runtime metadata가 없으면 local CLI config/cache를 사용한다.
3. CLI log에서만 확인되는 값은 medium confidence로 표시한다.
4. Trinity static config는 fallback일 뿐 actual model의 근거가 아니다.
5. Provider-native continuation은 `workflow_id + agent_name + lane + access + cwd_hash + resolved_model`에 묶는다.
6. Ambiguous continue flag는 자동화 기본값으로 쓰지 않는다.
7. Provider session이 없거나 resume 실패 시 canonical shared context 재주입으로 fallback한다.
8. Execution 권한이 달라지는 경우 같은 provider session을 무조건 재사용하지 않는다.

## 용어

- `workflow_id`: Trinity workflow id. 예: `wf-a1b2c3d4e5f6`.
- `request_id`: Trinity가 provider call마다 만든 id. 예: `round-1-claude-...`.
- `provider_session_id`: Claude native `session_id`처럼 provider가 대화 지속성에 쓰는 id.
- `provider_thread_id`: Codex JSONL `thread.started.thread_id`.
- `provider_conversation_id`: Antigravity `conversation=<uuid>`.
- `lane`: provider session을 분리하는 실행 맥락. 예: `deliberation`, `execution`, `review`, `synthesis`.
- `actual_model`: 이번 호출에서 실제 관측된 모델명 또는 가장 신뢰도 높은 local resolution 결과.
- `configured_model`: Trinity config에서 요청한 model 값.

## 데이터 모델

### ProviderSessionRef

Provider session state는 workflow session 안에 저장한다.

```python
@dataclass
class ProviderSessionRef:
    workflow_id: str
    agent_name: str
    provider: str
    lane: str
    access: str
    cwd: str
    provider_session_id: str = ""
    provider_thread_id: str = ""
    provider_conversation_id: str = ""
    first_request_id: str = ""
    last_request_id: str = ""
    invocation_count: int = 0
    status: str = "active"  # active | stale | failed | disabled
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    diagnostics: list[str] = field(default_factory=list)
```

Key 규칙:

```text
{agent_name}:{lane}:{access}:{cwd_hash}
```

예:

```text
claude:deliberation:read-only:7f12ab
codex:execution:workspace-write:7f12ab
antigravity:review:read-only:7f12ab
```

같은 agent라도 read-only deliberation과 workspace-write execution은 분리한다. Provider CLI가 session 안에 권한, cwd, tool state를 저장할 수 있기 때문이다.

### AgentRuntimeModel

```python
@dataclass
class AgentRuntimeModel:
    agent_name: str
    provider: str
    configured_model: str
    actual_model: str = ""
    model_label: str = ""
    provider_model_id: str = ""
    context_window: int = 0
    max_output_tokens: int = 0
    source: str = "unknown"
    confidence: str = "unknown"  # high | medium | low | unknown
    observed_request_id: str = ""
    observed_at: float = field(default_factory=time.time)
    diagnostics: list[str] = field(default_factory=list)
```

Source 값:

```text
runtime_metadata
local_cli_config
local_cli_cache
provider_log
trinity_config
unsupported
```

### WorkflowSession 확장

```python
@dataclass
class WorkflowSession:
    ...
    provider_sessions: dict[str, dict[str, Any]] = field(default_factory=dict)
    runtime_models: dict[str, dict[str, Any]] = field(default_factory=dict)
```

`provider_sessions`와 `runtime_models`는 archive/resume 대상에 포함되어야 한다. 사용자가 `/resume`으로 Trinity workflow를 복원하면 provider-native continuation도 가능한 범위에서 복원한다.

## Invocation 정책

### 공통 흐름

```text
build PromptRequest
-> resolve session key
-> if existing ProviderSessionRef is active: build resume command
-> else: build first-call command
-> invoke provider
-> parse provider ids and model metadata
-> update WorkflowSession.provider_sessions/runtime_models
-> persist event
```

Resume 실패 시:

```text
resume command failed
-> mark ProviderSessionRef.status = failed
-> record diagnostic
-> retry once with first-call command and canonical context
-> store new provider session id
```

### Claude

현재 first-call command:

```bash
claude \
  --model 'opus[1m]' \
  -p \
  --output-format json \
  --append-system-prompt '<role_prompt>' \
  --dangerously-skip-permissions \
  '<prompt>'
```

개선된 first-call command:

```bash
claude \
  --model 'opus[1m]' \
  -p \
  --output-format json \
  --append-system-prompt '<role_prompt>' \
  --dangerously-skip-permissions \
  '<prompt>'
```

첫 호출은 동일하게 시작해도 된다. 단, JSON 응답에서 `session_id`와 `modelUsage`를 파싱해 저장한다.

개선된 continuation command:

```bash
claude \
  --resume '<provider_session_id>' \
  --model 'opus[1m]' \
  -p \
  --output-format json \
  --append-system-prompt '<role_prompt>' \
  --dangerously-skip-permissions \
  '<prompt>'
```

정책:

- `claude -c -p`는 사용하지 않는다.
- `--resume <session_id>`를 기본 continuation으로 사용한다.
- `--resume`이 실패하면 새 `claude -p` call로 fallback하고 새 `session_id`를 저장한다.
- JSON `modelUsage`가 있으면 `actual_model`, `contextWindow`, `maxOutputTokens`, token usage를 갱신한다.
- `session_id`가 없으면 session continuity unavailable diagnostic을 남긴다.

선택적으로 `--session-id <uuid>`를 first-call에 사용할 수 있는지 contract test를 작성한다. 지원이 안정적이면 Trinity가 provider session UUID를 선생성해 더 deterministic하게 매핑할 수 있다. 초기 구현은 반환된 `session_id` 파싱 방식이 안전하다.

### Codex

Codex는 `stateless`와 `continuity` 두 mode를 분리한다.

Stateless one-shot command:

```bash
codex exec \
  --json \
  --ephemeral \
  --skip-git-repo-check \
  --sandbox read-only \
  --cd <cwd> \
  -
```

Prompt body는 stdin으로 전달한다. 이 mode는 기존 one-shot 동작과 호환되며 provider-native session을 이어가지 않는다. 반환된 `thread_id`는 diagnostics로 저장할 수 있지만 다음 호출의 continuation 근거로 사용하지 않는다.

Continuity mode first-call command:

```bash
codex exec \
  --json \
  --skip-git-repo-check \
  --sandbox read-only \
  --cd <cwd> \
  -
```

중요 변경점:

- `--ephemeral` 제거.
- JSONL `thread.started.thread_id` 저장.
- prompt body는 stdin으로 전달.

Continuation command:

```bash
codex exec resume \
  '<provider_thread_id>' \
  --json \
  --skip-git-repo-check \
  -
```

정책:

- JSONL `thread.started.thread_id`를 `provider_thread_id`로 저장한다.
- `codex exec resume --last`와 `--all`은 사용하지 않는다.
- `PROMPT` argv에는 `-`를 넣고 실제 prompt는 stdin으로 전달한다.
- provider session key는 `workflow_id + agent + lane + access + cwd_hash + resolved_model`로 계산한다.
- 같은 Codex `thread_id`는 같은 cwd, 같은 sandbox/access, 같은 logical lane에서만 재사용한다.
- Codex actual model은 우선순위로 해석한다.
  - JSONL에 model field가 생기면 runtime metadata로 사용한다.
  - 없으면 `~/.codex/config.toml`의 `model`을 읽는다.
  - 해당 model의 `context_window`는 `~/.codex/models_cache.json`에서 읽는다.
- `codex exec resume`이 cwd/sandbox를 어떻게 적용하거나 상속하는지 contract test를 통과하기 전에는 execution lane resume을 보수적으로 비활성화한다.
- Execution lane에서 `workspace-write`가 필요한 경우, first-call session과 resume session의 sandbox가 일관되는지 반드시 검증한다.
- `codex exec resume <thread_id>`가 실패하면 Trinity workflow는 유지하고 canonical context를 재주입해 새 continuity first-call을 시작한다. 이때 새 `thread_id`를 저장하고, 이전 thread resume 실패를 diagnostic event로 남긴다.

### Antigravity

Antigravity는 Codex와 같은 "provider session id를 Trinity workflow에 매핑한다"는 방향으로 간다. 차이는 id 관측 위치다. Codex는 stdout JSONL에서 `thread_id`를 얻고, Antigravity는 호출별 log file에서 `conversation=<uuid>`를 얻는다.

현재 first-call command:

```bash
agy \
  --print-timeout=<seconds>s \
  --sandbox \
  --print \
  '<prompt>'
```

개선된 first-call command:

```bash
agy \
  --log-file <state_dir>/provider-sessions/<request_id>.agy.log \
  --print-timeout=<seconds>s \
  --sandbox \
  --print \
  '<prompt>'
```

Continuation command:

```bash
agy \
  --log-file <state_dir>/provider-sessions/<request_id>.agy.log \
  --conversation '<provider_conversation_id>' \
  --print-timeout=<seconds>s \
  --sandbox \
  --print \
  '<prompt>'
```

정책:

- `agy --continue`는 사용하지 않는다. 가장 최근 conversation 기준이라 automation에 모호하다.
- `--conversation <uuid>`를 사용한다. 이 uuid는 Trinity가 저장한 `provider_conversation_id`여야 한다.
- `--log-file`을 항상 지정해서 global log race를 피한다.
- provider session key는 `workflow_id + agent + lane + access + cwd_hash + resolved_model`로 계산한다.
- 같은 `provider_conversation_id`는 같은 cwd, 같은 access/sandbox policy, 같은 logical lane에서만 재사용한다.
- 로그에서 `Print mode: conversation=<uuid>`를 파싱해 `provider_conversation_id`로 저장한다.
- 로그에서 `Propagating selected model override to backend: label="..."`를 파싱해 `model_label`로 저장한다.
- `agy --print -` 형태의 stdin prompt 계약은 확인되지 않았으므로, smoke test 통과 전까지 prompt는 positional argv로 전달한다.
- `--sandbox`는 boolean flag라 Codex의 `read-only | workspace-write`처럼 세분화된 sandbox level을 표현하지 못한다. Trinity access lane과 Antigravity sandbox policy를 별도 metadata로 저장한다.
- `agy --conversation <uuid>`가 실패하면 Trinity workflow는 유지하고 canonical context를 재주입해 새 first-call을 시작한다. 새 `conversation_id`를 저장하고 이전 conversation resume 실패를 diagnostic event로 남긴다.
- stdout에는 machine-readable metadata가 없으므로 context window는 `unsupported` 또는 수동 mapping table이 생기기 전까지 unknown으로 둔다.

## Budget 신뢰도 정책

Budget display는 숫자와 source를 함께 보여준다.

예시:

```text
Claude: GLM-5.1[1m] 1,000,000 context (runtime metadata, high)
Codex: GPT-5.5 272,000 context (local CLI cache, medium-high)
Antigravity: Gemini 3.5 Flash (Medium) context unknown (provider log, medium)
```

신뢰도 우선순위:

1. `runtime_metadata`: provider response가 actual model과 contextWindow를 직접 제공한다.
2. `local_cli_cache`: provider CLI의 model cache가 model slug와 context window를 제공한다.
3. `local_cli_config`: provider CLI config가 model selection을 제공한다.
4. `provider_log`: provider log가 selected model label을 제공한다.
5. `trinity_config`: Trinity 설정에 적힌 requested model 또는 fallback budget.
6. `unsupported`: 확인할 수 없음.

Budget checker는 `context_window > 0`인 경우에만 정확한 ratio를 표시한다. Unknown이면 ratio 대신 `unknown` 또는 `not reported`를 보여주고, conservative fallback threshold를 내부적으로만 사용한다.

## UI와 Report 표시

Provider card:

```text
Claude
Configured: opus[1m]
Actual: GLM-5.1[1m]
Context: 1,000,000 (runtime metadata)
Session: 3715bb9c...
```

Inspector `Providers` 또는 `Sessions` 섹션:

```text
Provider Sessions
- claude deliberation read-only: session_id=3715bb9c..., last_request=round-1-claude-...
- codex deliberation read-only: thread_id=019ea9e3..., last_request=round-1-codex-...
- antigravity deliberation read-only: conversation_id=9ab98524..., last_request=round-1-antigravity-...
```

Report export에는 configured/actual model과 provider session ids를 포함한다. 단, 전체 id는 diagnostics/report에서만 보여주고 카드 UI는 짧게 표시한다.

## Persistence와 Resume

Trinity `/resume`은 workflow state만 복원하는 것이 아니라 provider session mapping도 복원해야 한다.

복원 후 첫 provider 호출 흐름:

```text
load WorkflowSession
-> provider_sessions restored
-> provider session status active?
-> run lightweight resume readiness check? optional
-> send continuation command
```

Provider-native resume이 실패하면 세션은 망가진 것이 아니라 provider continuation만 실패한 것이다. Trinity workflow는 유지하고 canonical context 재주입으로 새 provider session을 시작한다.

## 테스트 계획

### Parser tests

- Claude JSON에서 `session_id`, `modelUsage`, `contextWindow`, usage를 추출한다.
- Codex JSONL에서 `thread.started.thread_id`와 `turn.completed.usage`를 추출한다.
- Codex local config/cache에서 `gpt-5.5`, `context_window=272000`을 resolve한다.
- Antigravity log에서 `conversation=<uuid>`와 selected model label을 추출한다.

### Command builder tests

- Claude first-call에는 `--resume`이 없다.
- Claude continuation에는 `--resume <session_id>`가 있고 `-c`가 없다.
- Codex continuity mode first-call에는 `--ephemeral`이 없다.
- Codex stateless mode first-call에는 기존처럼 `--ephemeral`을 유지할 수 있다.
- Codex prompt는 argv 문자열이 아니라 stdin으로 전달하고, command의 `PROMPT` 위치에는 `-`를 둔다.
- Codex continuation은 `codex exec resume <thread_id> --json ... -` 형태다.
- Codex continuation은 `--last`와 `--all`을 사용하지 않는다.
- Codex session key는 `workflow_id`, `agent`, `lane`, `access`, `cwd_hash`, `resolved_model`이 바뀌면 달라진다.
- Antigravity continuation은 `--conversation <uuid>`를 사용하고 `--continue`를 쓰지 않는다.
- Antigravity call은 `--log-file`을 지정한다.
- Antigravity prompt는 stdin 계약이 확인되기 전까지 positional argv로 전달한다.
- Antigravity session key는 `workflow_id`, `agent`, `lane`, `access`, `cwd_hash`, `resolved_model`이 바뀌면 달라진다.
- Antigravity access lane과 `--sandbox` boolean policy는 metadata에 분리해 저장한다.

### Workflow tests

- 새 workflow 시작 후 provider session refs가 비어 있다가 첫 응답 후 채워진다.
- 같은 workflow의 다음 round는 같은 provider session ref를 사용한다.
- 다른 workflow는 provider session을 공유하지 않는다.
- `read-only` lane과 `workspace-write` lane은 session key가 다르다.
- Codex execution lane resume은 cwd/sandbox contract test가 통과하기 전에는 비활성화된다.
- Antigravity conversation resume 실패 시 새 conversation으로 fallback하고 diagnostic event가 기록된다.
- `/resume`으로 workflow archive를 복원하면 provider session refs도 복원된다.
- Provider resume 실패 시 새 provider session으로 fallback하고 diagnostic event가 기록된다.

### UI tests

- Provider card가 configured model과 actual model을 구분해 표시한다.
- context budget source와 confidence가 inspector에 표시된다.
- unknown context window는 가짜 ratio로 표시하지 않는다.

## 구현 단계

1. Provider metadata model 추가
   - `ProviderSessionRef`
   - `AgentRuntimeModel`
   - `WorkflowSession.provider_sessions`
   - `WorkflowSession.runtime_models`

2. Provider parser 추가
   - Claude JSON parser
   - Codex JSONL thread/model resolver
   - Antigravity log parser

3. Command builder 확장
   - first-call vs continuation 분리
   - provider별 resume command 생성
   - `InvocationAccess`와 lane 기반 session key 계산
   - Codex stateless/continuity mode 분리
   - Codex prompt stdin 전달 지원
   - Antigravity conversation continuation command 생성
   - Antigravity prompt positional argv 전달 유지

4. Persistence 연결
   - provider metadata를 workflow session JSON에 저장
   - workflow event log에 provider session/model observation event 추가
   - Codex resume 실패 시 새 thread 생성과 diagnostic event 기록
   - Antigravity resume 실패 시 새 conversation 생성과 diagnostic event 기록

5. UI/Report 반영
   - provider card
   - inspector
   - `/context`
   - report export

6. Contract tests와 smoke tests
   - 실제 CLI가 설치된 환경에서는 optional smoke marker로 검증
   - CI에서는 fixture 기반 parser/command tests 실행

## 리스크와 결정 사항

### Claude `-c` 사용 여부

사용하지 않는다. `-c`는 current directory의 latest conversation을 기준으로 하므로 자동화에서 충돌 위험이 있다. Trinity는 `--resume <session_id>`만 사용한다.

### Codex `--ephemeral` 유지 여부

두 mode로 분리한다.

- `stateless`: 기존처럼 `--ephemeral` 유지.
- `continuity`: `--ephemeral` 제거하고 `thread_id`를 저장한다.

이번 작업의 목표는 continuity mode를 구현하는 것이다. 다만 Codex execution lane resume은 sandbox/cwd 적용 또는 상속 검증 전까지 read-only deliberation/review부터 적용한다.

`codex exec resume --last`와 `--all`은 사용하지 않는다. 자동화에서는 current directory의 최근 session이나 모든 directory의 session을 고르는 방식이 다른 Trinity workflow와 충돌할 수 있다.

`codex exec resume <thread_id>`가 실패하면 Trinity workflow를 실패 처리하지 않는다. canonical context를 재주입해 새 continuity first-call을 열고, 새 `thread_id`로 session mapping을 갱신한다. UI와 report에는 이전 thread resume 실패와 새 thread 생성 사실을 diagnostic으로 남긴다.

### Antigravity log parsing 안정성

Global log를 파싱하지 않는다. 모든 `agy` 호출에 `--log-file`을 지정하고 해당 파일만 파싱한다.

`agy --continue`는 사용하지 않는다. 가장 최근 conversation 기준이라 자동화에서 다른 workflow와 충돌할 수 있다. Trinity는 저장된 `provider_conversation_id`를 `agy --conversation <uuid>`로만 이어간다.

Antigravity prompt stdin 전달은 아직 기본 정책으로 채택하지 않는다. `agy --print -` 또는 동등한 stdin 입력 계약이 공식 문서나 로컬 smoke test로 확인되면 positional argv 전달을 stdin으로 전환할 수 있다.

Antigravity `--sandbox`는 boolean flag다. Codex처럼 `read-only`, `workspace-write`, `danger-full-access`를 flag 하나로 구분할 수 없으므로 Trinity의 `InvocationAccess`와 Antigravity의 `sandbox_enabled` 관측값을 분리해 저장한다.

### Actual model이 호출 중 바뀌는 경우

Provider fallback이나 model router가 실제 모델을 바꿀 수 있다. `AgentRuntimeModel`은 latest observation을 저장하고, response artifact metadata에는 request별 observation을 남긴다.

### Context window unknown 처리

Unknown 값을 임의로 1,000,000으로 표시하지 않는다. 내부 conservative fallback이 필요하면 `fallback_context_budget`과 `context_window_source=trinity_config`를 분리해 표시한다.

## 권장 결정

- Trinity workflow id는 provider session id를 대체하지 않는다.
- Provider session id는 `workflow_id + agent + lane + access + cwd_hash + resolved_model`에 매핑한다.
- Claude continuation은 `--resume <session_id> -p`를 사용한다.
- Codex stateless mode는 `--ephemeral`을 유지한다.
- Codex continuity mode는 `--ephemeral`을 제거하고 `codex exec resume <thread_id>`를 사용한다.
- Codex prompt는 command argv가 아니라 stdin으로 전달한다.
- Codex continuation은 `--last`, `--all` 없이 명시적 `thread_id`만 사용한다.
- Codex execution lane resume은 cwd/sandbox contract test 통과 후 활성화한다.
- Antigravity continuation은 `--conversation <conversation_id> --print`를 사용한다.
- Antigravity `--continue`는 사용하지 않는다.
- Antigravity 호출에는 `--log-file`을 지정하고 해당 로그에서 `conversation_id`와 model label을 파싱한다.
- Antigravity prompt는 stdin 계약 검증 전까지 positional argv로 전달한다.
- Antigravity `--sandbox` boolean은 Trinity `InvocationAccess`와 별도 metadata로 저장한다.
- Model display는 `configured_model`과 `actual_model`을 분리하고, Codex `default`는 `~/.codex/config.toml`과 local model cache를 해석해 실제 모델명으로 표시한다.
- Budget display는 source/confidence를 반드시 함께 보여준다.
