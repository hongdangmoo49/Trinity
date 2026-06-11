# Agent Model Selector CLI Discovery Design

작성일: 2026-06-10

브랜치: `feature/agent-model-selector-cli-discovery-design`

## 배경

`feature/agent-targeted-chat-design`에서 Start/Nexus 입력창 아래에 agent 선택
체크박스와 모델 드롭다운을 추가했다. 기능 흐름은 맞지만 현재 Textual UI에서는 다음
문제가 보인다.

1. Agent/model 선택 박스가 세로로 너무 크다. 입력창 아래 행은 보조 제어 영역이므로
   높이보다 가로 공간을 쓰는 편이 낫다.
2. Textual `Checkbox`와 `Select` 기본 장식이 그대로 노출되어 agent 사이에 의미 없는
   빈 박스처럼 보이는 요소가 생긴다.
3. 드롭다운의 첫 항목은 agent별 기본값이어야 한다. 예를 들어 `claude(default)`,
   `codex(default)`, `agy(default)`가 최상단에 있고, 아래 항목은 모델명만 보여야 한다.
4. 모델 항목은 정적 fallback만 쓰지 말고 가능한 경우 실제 provider CLI가 반환한
   현재 모델 목록으로 채워야 한다.

## 현재 구현

현재 UI는 `AgentRecipientModelSelector`가 담당한다.

- 파일: `src/trinity/textual_app/widgets/agent_recipient_model_selector.py`
- 구성: `Static` label + Textual `Checkbox` + Textual `Select`
- 모델 후보: `trinity.models.provider_model_choices(spec.provider)`
- 스타일: `src/trinity/textual_app/app.py`의 `.agent-recipient-selector`,
  `.recipient-agent-check`, `.recipient-agent-model`

모델 후보의 정적 원천은 `src/trinity/models.py`의
`PROVIDER_MODEL_CONTEXTS`다. 이 목록은 setup/settings 화면에서도 사용한다.

## CLI 실측 결과

2026-06-10 WSL 환경에서 확인한 명령은 다음과 같다.

### Codex

명령:

```bash
codex debug models
```

파싱 규칙:

- JSON의 `models[]`를 읽는다.
- `visibility == "list"`인 항목만 UI에 노출한다.
- 값은 `slug`, 표시명은 기본적으로 `display_name`보다 `slug`를 우선한다.
  사용자는 실제 실행에 들어가는 값을 알아야 하기 때문이다.

현재 출력에서 사용 가능한 모델:

```text
gpt-5.5
gpt-5.4
gpt-5.4-mini
gpt-5.3-codex-spark
```

fallback 명령:

```bash
codex debug models --bundled
```

### Antigravity

명령:

```bash
agy models
```

현재 출력:

```text
Gemini 3.5 Flash (Medium)
Gemini 3.5 Flash (High)
Gemini 3.5 Flash (Low)
Gemini 3.1 Pro (Low)
Gemini 3.1 Pro (High)
Claude Sonnet 4.6 (Thinking)
Claude Opus 4.6 (Thinking)
GPT-OSS 120B (Medium)
```

`agy --help` 기준 실행 시 모델 지정은 `--model` 플래그를 사용한다.

```bash
agy --model "Gemini 3.5 Flash (Medium)" --print "query"
```

### Claude

명령:

```bash
claude --help
```

확인된 사실:

- `claude --model <model>`은 존재한다.
- help 설명은 `sonnet`, `opus` alias 또는 full model name을 받는다고 말한다.
- Codex의 `debug models`나 Antigravity의 `models`처럼 비대화형 모델 목록을 출력하는
  CLI 명령은 현재 확인되지 않았다.

따라서 Claude는 이번 범위에서 다음 정책을 사용한다.

- 드롭다운 최상단에는 항상 `claude(default)`를 둔다.
- 아래 후보는 기존 `PROVIDER_MODEL_CONTEXTS`의 Claude fallback 목록을 사용하되,
  source를 `static-fallback`으로 표시 가능한 내부 metadata에 남긴다.
- 사용자가 명시 모델을 고르면 실행 시 `claude --model <value>`로 넘긴다.
- 추후 Anthropic Models API를 선택적 discovery source로 붙일 수 있지만, 이 작업의
  기본 요건인 "CLI가 반환한 목록"에는 해당하지 않으므로 별도 후속 과제로 둔다.

## 목표 UI

### 레이아웃

Start와 Nexus 모두 입력창 아래에 한 줄짜리 compact control row를 둔다.

```text
물어볼 대상: [x] 전체  [x] Claude  [Claude(default) v]  [x] Codex  [codex(default) v]  [x] Agy  [agy(default) v]
```

목표 크기:

- selector row 높이: 1-2 terminal row 안에 들어가야 한다.
- Start 입력창과 버튼 영역 사이에서 세로 공간을 크게 차지하지 않아야 한다.
- 가로 폭은 현재보다 약간 더 넓게 허용한다. Start shell은 88에서 96 안팎까지 확장할 수
  있다.
- 좁은 화면에서는 agent block 단위로 다음 줄로 wrap하되, dropdown 내부 텍스트가
  세로로 잘려 보이면 안 된다.

### 빈 박스 제거

Textual 기본 `Checkbox`와 `Select` 조합을 그대로 쓰지 않는다.

대안:

- `CompactAgentToggle`: `Button` 또는 `Static` 기반의 1-row toggle.
  값은 `[x] Claude`, `[ ] Claude`처럼 표시한다.
- `CompactModelDropdown`: collapsed 상태는 1-row button처럼 보이고, 열렸을 때만
  `OptionList` 또는 lightweight popup을 표시한다.

이렇게 하면 이미지에서 보이는 agent 사이의 얇은 빈 사각형과 큰 드롭다운 박스를 제거할
수 있다.

### 드롭다운 항목 규칙

각 agent dropdown의 option 순서는 항상 다음 규칙을 따른다.

1. 첫 항목: `<agent>(default)`
   - Claude: `claude(default)`
   - Codex: `codex(default)`
   - Antigravity: `agy(default)`
2. 이후 항목: 모델명만 표시
   - 예: `gpt-5.5`
   - 예: `Gemini 3.5 Flash (Medium)`
   - 예: `opus[1m]`

선택 값은 다음처럼 저장한다.

- default 항목 value: `default`
- live/static 모델 항목 value: 실제 CLI에 넘길 모델 문자열

`model_overrides()`는 선택된 agent 중 default가 아닌 모델만 반환한다. 이 정책은 현재
workflow session의 override 저장 방식과 맞다.

## 모델 발견 설계

새 모듈을 추가한다.

```text
src/trinity/providers/model_discovery.py
```

핵심 타입:

```python
@dataclass(frozen=True)
class ProviderModelChoice:
    provider: Provider
    model: str
    label: str
    source: Literal["cli-live", "cli-bundled", "static-fallback", "unavailable"]
    is_default: bool = False
    context_budget: int | None = None
```

핵심 API:

```python
def discover_provider_models(
    provider: Provider,
    cli_command: str,
    *,
    timeout_seconds: float = 3.0,
) -> list[ProviderModelChoice]:
    ...
```

Provider별 구현:

| Provider | Primary command | Parser | Fallback |
| :--- | :--- | :--- | :--- |
| Codex | `codex debug models` | JSON `models[].slug`, `visibility == "list"` | `codex debug models --bundled`, 이후 `PROVIDER_MODEL_CONTEXTS` |
| Antigravity | `agy models` | non-empty line list | `PROVIDER_MODEL_CONTEXTS` |
| Claude | 없음 | 없음 | `PROVIDER_MODEL_CONTEXTS` |

공통 규칙:

- 모든 목록의 첫 항목은 provider별 default sentinel이다.
- CLI discovery는 UI mount를 막지 않는다. selector는 fallback으로 먼저 렌더링하고,
  background discovery 결과가 오면 options를 갱신한다.
- discovery 실패는 notification으로 크게 띄우지 않는다. 대신 debug/local command
  surface에서 볼 수 있게 source/reason을 남긴다.
- CLI 목록은 session 중 짧게 cache한다. 기본 TTL은 5분으로 둔다.
- cache key는 `(provider, cli_command, version_hint)`로 둔다. version_hint는 가능하면
  `codex --version`, `agy --version`, `claude --version`에서 얻는다.

## UI 적용 흐름

1. `AgentRecipientModelSelector`는 생성 시 fallback options로 즉시 렌더링한다.
2. `TrinityTextualApp.on_mount()` 또는 screen mount 이후 background worker가
   provider별 model discovery를 실행한다.
3. discovery 결과가 도착하면 selector에 `set_model_choices(agent_name, choices)`를
   호출한다.
4. 현재 선택 값이 새 목록에 있으면 유지한다.
5. 현재 선택 값이 새 목록에 없으면 다음 규칙을 적용한다.
   - 값이 `default`이면 유지
   - session override 값이면 목록 끝에 `static-fallback` source로 추가해서 유지
   - otherwise `default`로 되돌리고 local command log에 reason을 남긴다.

## 실행 경로

현재 target model override는 다음 경로로 흐른다.

```text
AgentRecipientModelSelector.model_overrides()
-> StartScreen.Submitted / NexusScreen.FollowUpSubmitted
-> TrinityTextualApp
-> TextualWorkflowController
-> WorkflowEngine session.agent_model_overrides
-> TrinityOrchestrator(active_agent_names, agent_model_overrides)
```

이 경로는 유지한다. 변경 대상은 dropdown options를 채우는 방식과 compact UI뿐이다.

## 테스트 계획

### Parser tests

새 테스트 파일:

```text
tests/test_provider_model_discovery.py
```

검증:

- Codex JSON에서 `visibility == "list"`만 추출한다.
- Codex malformed JSON은 fallback으로 내려간다.
- Antigravity `agy models` line output을 순서대로 추출한다.
- 빈 줄과 중복 모델은 제거한다.
- Claude는 CLI list command가 없으므로 default + static fallback을 반환한다.
- 모든 provider 결과의 첫 항목은 `<agent>(default)` label을 가진 `default` value다.

### Widget tests

기존 `tests/test_textual_app.py`에 추가한다.

검증:

- Start/Nexus selector는 compact toggle/dropdown widget을 사용하고 raw `Checkbox`/large
  `Select`를 직접 노출하지 않는다.
- default option label이 agent별로 `claude(default)`, `codex(default)`, `agy(default)`다.
- default 아래 option label은 모델명만 표시한다.
- default 선택 시 `model_overrides()`에 포함되지 않는다.
- live discovery 결과를 주입하면 dropdown options가 갱신된다.

### Visual/Regression

Textual run test로 확인할 최소 조건:

- selector row의 height가 고정된 작은 값이다.
- agent 사이에 id 없는 빈 checkbox/select 박스가 생기지 않는다.
- 긴 Antigravity 모델명은 dropdown collapsed button 안에서 줄바꿈하지 않고 truncate한다.
- 열렸을 때 option list는 스크롤 가능해야 한다.

## 구현 순서

1. `ProviderModelChoice`와 provider별 parser를 추가한다.
2. Codex/Antigravity CLI discovery command runner를 추가하고 timeout/fallback을 넣는다.
3. Claude는 static fallback source로 명시한다.
4. `AgentRecipientModelSelector`를 compact toggle/dropdown 기반으로 바꾼다.
5. Start/Nexus selector에 discovery result 주입 경로를 연결한다.
6. 테스트를 추가한다.
7. 실제 WSL에서 `codex debug models`, `agy models` 출력 기반으로 수동 확인한다.

## 비범위

- Claude Models API 연동
- provider별 context budget을 live CLI에서 정확히 가져오는 기능
- 사용자가 settings 화면에서 provider별 기본 모델을 영구 저장하는 기능
- 모델 선택 UI 외의 resource overlay, execution, review workflow 변경
