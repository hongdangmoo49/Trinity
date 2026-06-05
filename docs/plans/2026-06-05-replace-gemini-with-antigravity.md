# Gemini 제거 및 Antigravity 전환 재설계

- Date: 2026-06-05
- Branch: `codex/replace-gemini-with-antigravity`
- Scope: 설계 문서만 작성한다. 구현은 별도 작업으로 진행한다.

## 배경

현재 Trinity의 새 기본 템플릿과 model-backed synthesis 경로는 `antigravity-cli`
및 `agy`를 기준으로 정리되어 있다. 하지만 실제 프로젝트 설정과 코드에는 여전히
`gemini-cli` 런타임 경로가 남아 있다.

현재 로컬 프로젝트 설정은 다음처럼 세 번째 에이전트를 Gemini로 실행한다.

```toml
[agents.gemini]
provider = "gemini-cli"
cli_command = "gemini"
enabled = true
```

따라서 `uv run trinity`는 현재 설정 기준으로 `gemini` 에이전트를 생성한다.
반면 템플릿과 `TrinityConfig.default_config()`는 이미 `antigravity` 에이전트와
`agy`를 기본 방향으로 삼는다.

공식 Antigravity CLI 문서 기준으로 설치 바이너리는 `agy`이고, 인증은 OS 보안
keyring 또는 브라우저/SSH OAuth 흐름을 사용한다. Antigravity CLI 설정 경로는
`~/.gemini/antigravity-cli/settings.json`이므로, 경로 안의 `.gemini` 문자열은
Google 측 제품 마이그레이션 흔적이지 Trinity가 Gemini CLI를 계속 지원해야 한다는
의미는 아니다.

참고 자료:

- https://antigravity.google/docs/cli-getting-started
- https://antigravity.google/docs/cli-install
- https://antigravity.google/docs/cli-using
- https://antigravity.google/docs/cli-reference

## 목표

1. Trinity의 세 번째 기본 에이전트 슬롯을 `gemini`에서 `antigravity`로 완전히
   전환한다.
2. 실제 provider 런타임은 `Provider.ANTIGRAVITY_CLI`와 `agy --print`만 사용한다.
3. 새 설정, 새 세션, 새 workflow, 새 테스트 fixture는 `antigravity` 이름을
   사용한다.
4. 기존 사용자의 `[agents.gemini] provider = "gemini-cli"` 설정은 깨뜨리지 않고
   `antigravity`로 마이그레이션한다.
5. Gemini CLI 실행 코드는 데드코드로 보고 제거한다.

## 비목표

- Antigravity CLI 자체의 모델 선택 UI 또는 `/model` 저장 구조를 Trinity가 직접
  재구현하지 않는다.
- `~/.gemini/antigravity-cli` 경로명을 억지로 바꾸지 않는다. 이 경로는
  Antigravity 공식 설정 경로다.
- 이미 저장된 과거 `shared.md`, session archive, workflow history 안의 문자열을
  전부 소급 수정하지 않는다. 새 런타임과 새 설정만 canonical하게 전환한다.
- `agy`의 machine-readable output 계약이 생기기 전까지 JSON/token usage를
  임의로 추정하지 않는다.

## 현재 영향 범위

### 런타임 provider

- `src/trinity/models.py`
  - `Provider.GEMINI_CLI`가 아직 존재한다.
  - Gemini 모델 컨텍스트 메타데이터가 남아 있다.
- `src/trinity/agents/factory.py`
  - `Provider.GEMINI_CLI`면 `trinity.legacy.gemini.agent.GeminiAgent`를 생성한다.
  - tmux interactive detector도 Gemini completion marker를 사용한다.
- `src/trinity/legacy/gemini/`
  - 실제 `gemini` CLI subprocess 및 tmux wrapper가 남아 있다.
- `src/trinity/agents/gemini_agent.py`
  - legacy Gemini wrapper shim이다.

### 설정 및 초기화

- `src/trinity/config.py`
  - default config는 이미 `antigravity`를 생성한다.
- `templates/trinity.config.example`
  - 이미 `[agents.antigravity] provider = "antigravity-cli" cli_command = "agy"`다.
- `.trinity/trinity.config`
  - 현재 로컬 프로젝트는 아직 `[agents.gemini]`를 사용한다.
- `src/trinity/setup/detector.py`
  - `agy`와 `gemini`를 모두 탐지한다.
  - Gemini는 legacy provider로 경고를 표시한다.
- `src/trinity/setup/wizard.py`
  - 설치된 legacy Gemini가 있으면 여전히 선택 가능한 provider로 노출될 수 있다.

### 역할/분배/워크플로우

- `src/trinity/i18n.py`
  - `antigravity`와 `gemini`가 동일 reviewer 역할로 공존한다.
- `src/trinity/tui/theme.py`
  - `antigravity`, `gemini` 테마가 둘 다 있다.
- `src/trinity/workflow/decomposer.py`
  - provider priority와 validation focus에 `antigravity`, `gemini`가 모두 있다.
- `src/trinity/workflow/execution.py`
  - fallback priority에 `gemini`가 남아 있다.
- `src/trinity/deliberation/distributor.py`
  - 기본 strength mapping은 아직 `gemini` 중심이다.

### 상태/인증/격리

- `src/trinity/workspace/managed_home.py`
  - `antigravity-cli`는 `.gemini/antigravity-cli`를 만든다. 이는 유지한다.
  - `gemini-cli`는 `.config/gemini`를 만든다. Gemini 제거 후에는 legacy
    migration 테스트 외에는 필요 없다.
- `src/trinity/providers/readiness.py`
  - Gemini auth/prompt 패턴과 Antigravity auth/prompt 패턴이 모두 있다.
  - Gemini 패턴은 legacy config migration 안내에만 필요하다.
- `src/trinity/context/monitor.py`
  - Gemini usage parser 이름이 남아 있다. 현재 one-shot provider usage 수집
    방향과 맞지 않으면 제거하거나 provider-neutral 이름으로 바꾼다.

### 테스트

테스트에는 두 종류의 `gemini`가 섞여 있다.

1. 실제 Gemini provider를 검증하는 테스트
   - `tests/test_gemini_agent.py`
   - `tests/test_agent_factory.py`의 Gemini 생성/interactive detector 테스트
   - `tests/test_multi_provider.py`의 Gemini provider 테스트
   - `tests/test_provider_readiness.py`의 Gemini auth 상태 테스트

2. 단순히 세 번째 reviewer agent 이름으로 `gemini`를 사용한 테스트
   - consensus, workflow, execution, shared context, peer review 계열
   - 이들은 provider 의미가 없으므로 `antigravity`로 치환하는 편이 맞다.

## 설계 결정

### 1. canonical 세 번째 agent 이름은 `antigravity`

새 코드와 새 설정에서 reviewer agent는 다음 형태만 사용한다.

```toml
[agents.antigravity]
provider = "antigravity-cli"
cli_command = "agy"
model = "default"
enabled = true
workspace_mode = "inplace"
context_budget = 1000000
```

TUI 표시는 기존 세 번째 슬롯을 유지하되 이름과 provider를 `antigravity`로 바꾼다.
즉 사용자가 보던 `claude / codex / gemini` 3자 구조는
`claude / codex / antigravity`가 된다.

### 2. Gemini CLI는 런타임 provider에서 제거

`Provider.GEMINI_CLI`는 최종적으로 제거한다. 다만 config migration을 위해 문자열
상수 또는 별도 deprecated-provider normalizer는 한 릴리스 동안 둘 수 있다.

권장 구조:

- `Provider` enum에는 active provider만 둔다.
  - `claude-code`
  - `codex`
  - `antigravity-cli`
- deprecated provider 문자열은 enum이 아니라 config/setup migration 계층에서
  처리한다.
  - `"gemini-cli"` -> `"antigravity-cli"`
  - agent key `"gemini"` -> `"antigravity"`
  - `cli_command = "gemini"` -> `"agy"`

이렇게 해야 factory에서 실수로 Gemini 런타임을 만들 가능성이 사라진다.

### 3. 기존 config는 자동 마이그레이션

`TrinityConfig.load()` 또는 그 전 단계에서 raw TOML dict를 normalize한다.

마이그레이션 규칙:

1. `[agents.gemini] provider = "gemini-cli"`가 있고 `[agents.antigravity]`가 없으면:
   - key를 `agents.antigravity`로 이동한다.
   - `name = "antigravity"`로 보정한다.
   - `provider = "antigravity-cli"`로 보정한다.
   - `cli_command = "agy"`로 보정한다.
   - role prompt가 기본 Gemini reviewer 문구면 Antigravity reviewer 문구로 교체한다.
   - 사용자가 직접 수정한 role prompt면 그대로 보존한다.
2. `[agents.gemini]`와 `[agents.antigravity]`가 둘 다 있으면:
   - `antigravity`를 우선한다.
   - `gemini`는 disabled legacy entry로도 유지하지 않는다.
   - 충돌 사실을 warning/diagnostic으로 남긴다.
3. `provider = "gemini-cli"`가 `gemini`가 아닌 임의 agent key에 있으면:
   - agent key는 유지할 수 있지만 provider/command는 `antigravity-cli`/`agy`로 바꾼다.
   - 단, 기본 세 번째 슬롯 문서와 init 출력은 `antigravity`를 권장한다.

저장 시에는 항상 canonical 형태로 쓴다. 즉 한번 `trinity config` 또는 `trinity init`
경로를 거치면 `.trinity/trinity.config`에서 `gemini-cli`가 사라져야 한다.

### 4. setup wizard는 Gemini를 선택지로 제공하지 않음

탐지기는 `gemini` 바이너리를 migration hint 용도로만 감지할 수 있다. 하지만
wizard의 agent 선택 단계에는 Gemini CLI를 provider 후보로 내보내지 않는다.

동작:

- `agy` 감지 성공: `Antigravity CLI`를 선택 가능하게 표시한다.
- `gemini`만 감지됨: Gemini CLI는 deprecated로 표시하고, `agy` 설치 및
  `agy plugin import gemini` 안내를 보여준다. 선택 가능한 agent로 만들지 않는다.
- `agy`와 `gemini`가 모두 감지됨: `agy`만 선택 가능하고, Gemini는 migration hint로만
  표시한다.

### 5. workflow 분배 규칙은 `antigravity` 중심으로 정리

`BlueprintDecomposer`, `ExecutionProtocol`, `TaskDistributor`의 provider priority와
reviewer strength mapping에서 `gemini`를 제거한다.

권장 priority:

```python
("codex", "claude", "antigravity")
```

review/validation/test/research 키워드는 `antigravity`에만 매핑한다.

과거 workflow history에 owner가 `gemini`로 남아 있는 경우는 실행 시점 fallback에서
처리한다. 예를 들어 current agents에 `gemini`가 없고 `antigravity`가 있으면
legacy owner alias로 `antigravity`를 선택한다.

### 6. Antigravity interactive tmux는 계속 비활성

현재 Antigravity wrapper는 one-shot `agy --print` 기반이다. factory는
`Provider.ANTIGRAVITY_CLI`의 interactive tmux 생성을 계속 거부한다.

이는 현재 아키텍처 방향과 맞다.

- 기본 transport는 `one-shot`
- tmux는 legacy/debug transport
- `agy`는 `AntigravityPrintAgent` + `AntigravityPrintInvoker`로 호출

### 7. response cleaner는 최소 호환만 유지

Gemini CLI 런타임 제거 후에도 다음 패턴은 당분간 남겨도 된다.

- `gemini-cli-migration` 안내 제거
- legacy output heading sanitizer

하지만 agent heading 패턴은 `antigravity`를 포함하도록 바꾼다.

```python
r"^### (?:claude|codex|antigravity)\b"
```

기존 `gemini` heading은 archived output 정리를 위해만 남길지 결정한다. 기본값은
새 출력 기준으로 제거하고, migration cleaner 테스트만 별도로 둔다.

## 구현 순서

### 1단계: 현재 프로젝트 설정 마이그레이션

- `.trinity/trinity.config`의 `[agents.gemini]`를 `[agents.antigravity]`로 바꾼다.
- `provider = "antigravity-cli"`, `cli_command = "agy"`로 바꾼다.
- role prompt는 reviewer 역할을 유지한다.
- 이 변경은 로컬 실행 기준을 즉시 바로잡는다.

검증:

- `uv run trinity status`
- `/status`에서 세 번째 agent가 `antigravity / antigravity-cli`로 표시되는지 확인

### 2단계: config migration 계층 추가

- `TrinityConfig._from_dict()` 앞에 deprecated agent/provider normalizer를 추가한다.
- old config 입력에 대한 테스트를 추가한다.
- canonical save 결과에서 `gemini-cli`가 사라지는지 확인한다.

대상 테스트:

- `tests/test_config.py`
- `tests/test_cli.py`
- `tests/test_setup_wizard.py`

### 3단계: setup detector/wizard 정리

- detection은 `agy`를 primary로 둔다.
- Gemini detection은 selectable provider가 아니라 migration warning으로만 표시한다.
- `LEGACY_PROVIDERS`는 enum 제거 전까지 유지하거나, enum 제거 후 문자열 기반 legacy
  detector로 분리한다.

대상 테스트:

- `tests/test_cli_detector.py`
- `tests/test_setup_wizard.py`
- `tests/test_e2e.py`

### 4단계: Gemini runtime 제거

- `Provider.GEMINI_CLI` 제거 또는 deprecated 문자열 처리로 이동
- `src/trinity/legacy/gemini/` 제거
- `src/trinity/agents/gemini_agent.py` 제거
- `AgentFactory`에서 Gemini 생성/interactive detector 제거
- provider model contexts에서 Gemini 모델 목록 제거

대상 테스트:

- `tests/test_agent_factory.py`
- `tests/test_gemini_agent.py` 삭제 또는 Antigravity 테스트로 대체
- `tests/test_multi_provider.py`
- `tests/test_models.py`

### 5단계: 역할/분배/워크플로우 이름 정리

- `i18n.ROLE_PROMPTS`에서 `gemini` 제거
- `localized_roles*` 반환값을 `claude`, `codex`, `antigravity`로 고정
- `tui/theme.py`에서 `gemini` 제거
- `BlueprintDecomposer`, `ExecutionProtocol`, `TaskDistributor`에서 `gemini` 제거
- old owner alias `gemini -> antigravity`는 execution fallback 또는 workflow migration에만 둔다.

대상 테스트:

- `tests/test_i18n.py`
- `tests/test_blueprint_decomposer.py`
- `tests/test_execution_protocol.py`
- `tests/test_workflow_engine.py`
- `tests/test_peer_review.py`

### 6단계: readiness/response cleaner 정리

- Antigravity readiness 패턴을 유지한다.
- Gemini readiness 테스트는 migration warning 테스트로 축소한다.
- response cleaner의 active agent heading에는 `antigravity`를 포함한다.

대상 테스트:

- `tests/test_provider_readiness.py`
- `tests/test_response_cleaner.py`

### 7단계: 문서와 changelog 정리

- README, template, checkpoint, plan/test-result 문서의 현재 provider 설명을
  `antigravity`로 통일한다.
- 과거 설계 문서의 historical mention은 수정하지 않아도 된다.
- 새 결과 문서에는 제거된 파일/남긴 compatibility surface를 명확히 기록한다.

## 병렬 작업 가능성

병렬 가능:

- config migration 테스트 작성
- setup wizard/detector 정리
- workflow 분배 규칙 테스트 치환
- 문서 정리

순차 필요:

1. Provider enum/runtime 제거는 config migration 설계가 먼저 들어간 뒤 해야 한다.
2. `legacy/gemini` 삭제는 factory와 테스트가 모두 Antigravity 기준으로 바뀐 뒤 해야 한다.
3. `.trinity/trinity.config` 마이그레이션은 테스트와 별개로 먼저 해도 되지만, 실제
   smoke test는 코드 migration 이후 다시 해야 한다.

## 리스크

1. 기존 사용자의 `.trinity/trinity.config`가 `gemini-cli`면 enum 제거 후 바로
   load failure가 날 수 있다. 그래서 raw config migration이 먼저 필요하다.
2. 테스트에서 `gemini`가 provider 의미인지 단순 agent fixture인지 섞여 있다.
   일괄 치환하면 의도치 않은 coverage 손실이 생긴다.
3. Antigravity 공식 설정 경로에 `.gemini`가 포함되므로 문자열 검색만으로
   Gemini 잔재를 판단하면 오탐이 생긴다.
4. `agy --print`의 token usage와 machine-readable output은 아직 안정 계약이 없다.
   Antigravity provider는 plain stdout + fallback 중심으로 유지해야 한다.
5. tmux transport에서 Antigravity interactive를 강제로 켜면 completion detection과
   auth/trust UI 문제가 다시 생길 수 있다.

## 완료 기준

- `uv run trinity status`에서 기본 세 번째 agent가 `antigravity`로 표시된다.
- 새 `trinity init` 결과에 `gemini-cli` provider가 생성되지 않는다.
- 기존 `[agents.gemini] provider = "gemini-cli"` 설정을 읽으면 canonical
  `antigravity-cli` 설정으로 마이그레이션된다.
- `AgentFactory`가 Gemini CLI runtime wrapper를 만들 수 없다.
- `src/trinity/legacy/gemini/`와 `src/trinity/agents/gemini_agent.py`가 제거된다.
- active code grep 기준으로 `gemini-cli`는 migration warning, docs historical note,
  Antigravity 공식 경로 설명 외에는 남지 않는다.
- 전체 테스트가 통과한다.

## 권장 커밋 단위

1. `docs: Gemini 제거 및 Antigravity 전환 설계 추가`
2. `chore: 로컬 Trinity 설정을 Antigravity로 전환`
3. `feat: legacy Gemini config를 Antigravity로 마이그레이션`
4. `refactor: Gemini runtime provider 제거`
5. `refactor: reviewer agent 명칭을 Antigravity로 통일`
6. `test: Antigravity 전환 테스트 정리`
7. `docs: Antigravity 전환 결과 기록`

## 다음 작업 제안

다음 구현은 1단계와 2단계를 먼저 묶는 것이 좋다. 현재 사용자가 실제로 실행하는
`.trinity/trinity.config`가 `gemini`를 가리키고 있으므로, 로컬 실행 기준과
config migration 기준을 먼저 맞춘 뒤 runtime 제거를 진행해야 안전하다.
