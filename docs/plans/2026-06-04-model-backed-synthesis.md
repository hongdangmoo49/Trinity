# Model-backed Central Synthesis 리팩터링 설계

## 배경

현재 중앙 synthesis는 `HeuristicSynthesisAgent`가 에이전트 응답에서 `VOTE`, `BLUEPRINT`, `OPEN QUESTIONS`를 규칙 기반으로 파싱해 합의 여부와 다음 질문을 만든다. 이 방식은 빠르고 비용이 없지만, 에이전트 응답 형식이 조금만 흔들려도 다음 대화 상태가 불안정해진다.

특히 세션형 UI에서는 중앙 synthesis가 사용자에게 보여줄 질문과 선택지를 안정적으로 만들어야 한다. 파싱 실패로 질문이 누락되거나 blueprint가 잘못 선택되면 사용자는 "대화가 이어지는 세션"이 아니라 "매번 새로 해석되는 도구"처럼 느끼게 된다.

## 목표

- 중앙 synthesis를 사용자가 이미 구독/인증한 provider CLI의 빠른 one-shot 모델로 실행한다.
- 모델 synthesis는 에이전트들의 자유로운 응답을 정규화된 `SynthesisResult`로 변환한다.
- 기존 heuristic parser는 제거하지 않고 fallback으로 유지한다.
- 새 synthesis agent는 deliberation 참가자가 아니라 중앙 조정자 역할만 한다.
- provider auth는 기존 사용자 PC의 CLI 로그인 상태를 그대로 사용한다.
- 실패해도 workflow가 멈추지 않도록 deterministic fallback과 diagnostics를 남긴다.

## 비목표

- provider별 최신 fastest model 이름을 코드에 강하게 박지 않는다.
- Claude/Codex/Antigravity의 내부 성능 순위를 Trinity가 임의 추정하지 않는다.
- 기존 agent 응답 계약을 완전히 제거하지 않는다.
- 실행 work package dispatch 구조는 이번 리팩터링 범위에 포함하지 않는다.

## 제안 구조

### 1. SynthesisAgent 계층

기존 인터페이스는 유지한다.

```python
class SynthesisAgent(Protocol):
    async def synthesize(self, synthesis_input: SynthesisInput) -> SynthesisResult:
        ...
```

추가할 구현:

- `ModelBackedSynthesisAgent`
  - 선택된 provider one-shot invoker를 호출한다.
  - strict JSON schema 출력을 요구한다.
  - 출력 검증 후 `SynthesisResult`로 변환한다.

- `FallbackSynthesisAgent`
  - primary: `ModelBackedSynthesisAgent`
  - fallback: `HeuristicSynthesisAgent`
  - 모델 호출 실패, timeout, auth failure, JSON validation failure 시 fallback 사용

기본 wire-up:

```text
auto mode:
  ModelBackedSynthesisAgent(selected fast provider)
  -> invalid/fail
  HeuristicSynthesisAgent

heuristic mode:
  HeuristicSynthesisAgent only
```

### 2. 설정

`[deliberation]` 아래에 synthesis 설정을 추가한다.

```toml
[deliberation]
synthesis_mode = "auto"        # auto | model | heuristic
synthesis_agent = ""           # optional: claude | codex | antigravity
synthesis_model = "fast"       # fast | default | provider-specific model
synthesis_timeout_seconds = 30
synthesis_max_input_chars = 60000
```

의미:

- `auto`
  - 사용 가능한 active provider 중 synthesis에 적합한 one-shot provider를 선택한다.
  - provider가 준비되지 않았거나 응답이 invalid면 heuristic fallback을 사용한다.

- `model`
  - 모델 synthesis를 우선한다.
  - 실패 시에도 안전을 위해 heuristic fallback은 사용하되, diagnostics에 실패 사유를 명확히 기록한다.

- `heuristic`
  - 현재 방식 그대로 deterministic parser만 사용한다.

### 3. Provider 선택 정책

선택 우선순위:

1. `synthesis_agent`가 지정되어 있고 enabled이면 해당 agent 사용
2. active agents 중 one-shot provider 사용 가능 여부 확인
3. provider readiness가 ready인 agent 우선
4. `synthesis_model = "fast"`이면 provider별 fast profile 사용
5. fast profile이 없으면 해당 agent의 configured model 또는 provider default 사용

중요한 원칙:

- Trinity가 사용자 대신 새 API key나 별도 auth를 요구하지 않는다.
- 기존 agent의 `cli_command`, `cwd`, `env_overrides`, `provider_state_mode`를 재사용한다.
- synthesis provider는 라운드 참가자로 표시하지 않고 별도 `synthesis` source로 기록한다.

### 4. Synthesis prompt contract

모델에게는 자유 응답이 아니라 JSON만 요구한다.

입력:

- original user prompt
- round number
- previous synthesis summary
- recorded user decisions
- usable agent opinions
- invalid response diagnostics 요약
- output JSON schema

출력 schema 초안:

```json
{
  "consensus_reached": true,
  "agreement_count": 2,
  "total_agents": 3,
  "summary_for_shared_md": "합의 요약",
  "next_round_prompt": "",
  "open_questions_for_user": [
    {
      "id": "q-001",
      "question": "사용자에게 물을 질문",
      "options": ["A", "B"],
      "recommended_option": "A",
      "blocking": true,
      "raised_by": ["codex"],
      "rationale": "질문이 필요한 이유"
    }
  ],
  "recommended_blueprint": {
    "title": "Blueprint title",
    "summary": "Blueprint summary",
    "architecture": [],
    "data_flow": [],
    "external_dependencies": [],
    "risks": [],
    "acceptance_criteria": [],
    "open_questions": []
  },
  "votes": {
    "claude": {
      "vote": "approve",
      "rationale": "..."
    }
  },
  "diagnostics": []
}
```

검증 규칙:

- `summary_for_shared_md`는 비어 있으면 안 된다.
- `total_agents`는 usable opinions 수와 일치해야 한다.
- `open_questions_for_user`가 있으면 `consensus_reached=false`로 정규화한다.
- `recommended_blueprint`가 없으면 execution work package를 만들지 않는다.
- blueprint가 invalid면 consensus를 false로 낮추거나 fallback한다.

### 5. JSON 실패 처리

모델 출력은 다음 순서로 처리한다.

1. 전체 stdout에서 JSON object 추출
2. schema validation
3. `SynthesisResult` 변환
4. 실패 시 diagnostics 기록
5. heuristic fallback 실행

선택적으로 1회 repair prompt를 둘 수 있다. 다만 초기 구현에서는 repair 없이 fallback하는 편이 단순하고 안전하다.

### 6. shared.md 기록

`Round N Synthesis`에는 다음을 남긴다.

```markdown
## Round 1 Synthesis
- source: model-backed
- provider: codex
- model: fast
- fallback_used: false

### Summary
...

### Next Round Prompt
...
```

fallback 사용 시:

```markdown
- source: heuristic
- fallback_used: true
- fallback_reason: model synthesis returned invalid JSON
```

모델 raw output은 response artifact와 별도 synthesis artifact로 저장하는 것이 좋다.

```text
.trinity/synthesis/round-01/synthesis.raw.txt
.trinity/synthesis/round-01/synthesis.json
```

### 7. TUI 표시

상태 패널에는 다음 정도만 표시한다.

```text
Synthesis: model-backed codex/fast
Fallback: no
```

질문이 있으면 기존 세션형 UI가 바로 질문 선택 UI를 보여준다.

## 구현 순서

1. 설정 모델 추가
   - `synthesis_mode`
   - `synthesis_agent`
   - `synthesis_model`
   - `synthesis_timeout_seconds`
   - `synthesis_max_input_chars`

2. `ModelBackedSynthesisAgent` 추가
   - prompt builder
   - provider request builder
   - JSON extraction/validation
   - `SynthesisResult` conversion

3. Orchestrator wire-up
   - active agent launch context 재사용
   - selected provider wrapper 또는 invoker 생성
   - `FallbackSynthesisAgent(primary=model, fallback=heuristic)`로 protocol에 주입

4. artifact 저장
   - raw model output
   - parsed JSON
   - diagnostics

5. TUI/status 표시
   - synthesis source/provider/model/fallback 표시

6. 테스트
   - valid model JSON -> structured consensus
   - open questions -> `needs_user_decision`
   - invalid JSON -> heuristic fallback
   - provider timeout -> heuristic fallback
   - `synthesis_mode="heuristic"` -> provider 호출 없음
   - `synthesis_agent` override

## 위험과 대응

- 모델 synthesis가 너무 느릴 수 있다.
  - timeout을 짧게 두고 fallback한다.

- 모델이 JSON 이외 텍스트를 섞을 수 있다.
  - JSON object extraction 후 validation한다.

- provider auth가 없을 수 있다.
  - readiness gate 결과를 활용하고 fallback한다.

- 모델이 합의를 과도하게 낙관할 수 있다.
  - `open_questions`가 있으면 무조건 consensus false로 정규화한다.
  - usable opinions 수와 votes 수를 검증한다.

- 비용/토큰이 늘 수 있다.
  - `synthesis_max_input_chars`로 agent opinions를 제한한다.
  - 이전 라운드는 synthesis summary 중심으로 전달한다.

## 결론

중앙 synthesis는 모델 기반으로 바꾸는 것이 세션형 UI와 잘 맞는다. 다만 parser를 제거하면 provider 실패 시 workflow가 멈출 수 있으므로, 기존 `HeuristicSynthesisAgent`는 fallback으로 유지해야 한다.

권장 기본값은 `synthesis_mode="auto"`다. 사용자가 이미 구독/인증한 provider의 빠른 one-shot 모델을 먼저 사용하고, 실패하면 deterministic parser로 계속 진행한다.
