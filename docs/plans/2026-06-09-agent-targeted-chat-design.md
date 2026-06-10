# Agent Targeted Chat Recipient Design

작성일: 2026-06-09

브랜치: `feature/agent-targeted-chat-design`

상태: 설계

## 목적

Nexus 채팅창에서 매번 세 에이전트 전체에게 묻는 방식만 제공하면, 사용자는 특정 에이전트의 관점만 빠르게 확인하거나 두 에이전트만 비교하고 싶을 때 불필요하게 전체 deliberation을 돌려야 한다.

이번 설계는 채팅 입력창 주변에 에이전트 체크박스를 제공해서, 사용자가 선택한 에이전트에게만 이번 질문을 보낼 수 있게 하는 UX와 내부 라우팅 구조를 정의한다.

## 결론

적용 가능하다.

가장 좋은 기본 UX는 slash command 중심이 아니라 첫 페이지와 Nexus 페이지의 입력창 바로 위 또는 안쪽 상단에 `All`, `Claude`, `Codex`, `Antigravity` 체크박스형 recipient selector를 두는 방식이다.

각 agent 항목은 단순 label이 아니라 `체크박스 + agent 이름 버튼 + 현재 모델` 조합으로 둔다. 체크박스는 이번 질문을 보낼 대상을 정하고, agent 이름을 누르면 dropdown이 열려 해당 agent가 이번 요청에서 사용할 모델을 선택한다.

이유는 다음과 같다.

- 사용자가 질문을 쓰는 순간 “누구에게 보낼지”를 같은 시야에서 결정할 수 있다.
- `/agent`는 이미 세션의 에이전트 활성화/비활성화 설정 명령이라, 이번 질문의 수신자 선택과 의미가 충돌한다.
- `/ask claude ...` 같은 명령만 제공하면 discoverability가 낮고, 일반 채팅 UX와 멀어진다.
- 체크박스 선택 상태와 모델 선택 상태를 footer나 provider panel보다 입력창에 붙이는 편이 행동 결과를 예측하기 쉽다.

slash command는 보조 기능으로만 둔다. 예를 들어 `/ask claude,codex <prompt>` 또는 `/to claude,codex`는 키보드 중심 사용자와 테스트 자동화를 위한 shortcut으로 제공할 수 있지만, 주 동선은 체크박스 UI다.

## 현재 구조 분석

### 입력 흐름

- [src/trinity/textual_app/widgets/composer.py](/home/user/workspace/Trinity/src/trinity/textual_app/widgets/composer.py)
  - `PromptComposer.Submitted`는 현재 `text`만 전달한다.
  - slash command palette, paste summary, multi-line 입력은 이 컴포넌트에 이미 들어 있다.
- [src/trinity/textual_app/screens/start.py](/home/user/workspace/Trinity/src/trinity/textual_app/screens/start.py)
  - 첫 화면의 `StartScreen.Submitted`는 `prompt`, `workspace_candidate`만 전달한다.
  - 첫 prompt는 `TrinityTextualApp.on_start_screen_submitted()`에서 workflow start로 들어간다.
- [src/trinity/textual_app/screens/nexus.py](/home/user/workspace/Trinity/src/trinity/textual_app/screens/nexus.py)
  - `NexusScreen.FollowUpSubmitted`는 `text`만 전달한다.
  - `_submit_follow_up()`는 일반 입력을 `FollowUpSubmitted(cleaned)`로 올리고, slash command는 `SlashCommandSubmitted`로 분리한다.
- [src/trinity/textual_app/app.py](/home/user/workspace/Trinity/src/trinity/textual_app/app.py)
  - Start 입력은 `workflow_controller.start_prompt(event.prompt, ...)`로 전달된다.
  - Nexus follow-up은 `workflow_controller.submit_follow_up(event.text)`로 전달된다.

### workflow와 agent 선택

- [src/trinity/textual_app/workflow_controller.py](/home/user/workspace/Trinity/src/trinity/textual_app/workflow_controller.py)
  - `_active_agent_names()`는 현재 `config.active_agents.keys()` 전체를 반환한다.
  - `start_prompt()`와 `submit_follow_up()`는 이 전체 active agent 목록을 `WorkflowEngine`에 넘긴다.
  - `_start_deliberation(prompt)`는 `TrinityOrchestrator(self.config, ...)`를 그대로 생성한다.
- [src/trinity/workflow/engine.py](/home/user/workspace/Trinity/src/trinity/workflow/engine.py)
  - `WorkflowSession.active_agents`는 workflow에 붙은 기본 에이전트 목록이다.
  - `start(goal, active_agents)`는 workflow의 기본 active agents를 저장한다.
  - `continue_from_blueprint(instruction, active_agents)`는 active agent가 있으면 session active agents를 갱신한다.
- [src/trinity/orchestrator.py](/home/user/workspace/Trinity/src/trinity/orchestrator.py)
  - 실제 wrapper 생성은 `config.active_agents`를 기준으로 한다.
  - `DeliberationProtocol`에는 생성된 `agents` dict 전체가 들어간다.

따라서 UI에서 체크박스만 숨기거나 provider panel만 필터링하는 것으로는 부족하다. 실제 provider 호출을 줄이려면 요청 단위의 `selected_agents`를 `TextualWorkflowController`까지 전달하고, 해당 run에 쓰는 orchestrator config 또는 active agent view를 부분집합으로 제한해야 한다.

## UX 설계

### 기본 배치

첫 페이지와 Nexus 화면 모두 입력창 바로 위에 한 줄 recipient/model bar를 둔다.

```text
Ask: [x] All  [x] Claude ▾ sonnet  [x] Codex ▾ default  [x] Antigravity ▾ default
Reply, refine direction, or type / for commands
```

터미널 폭이 좁으면 두 줄로 접는다.

```text
Ask: [x] All
[x] Claude ▾ sonnet      [x] Codex ▾ default
[x] Antigravity ▾ default
```

Start 화면에도 동일한 selector를 넣는다. 단, 첫 화면에서는 기본적으로 `All`이 켜져 있어야 한다. 첫 prompt를 한 에이전트에게만 보내면 Trinity의 기본 협의 경험과 다르므로, 일부만 선택된 경우 Nexus 진입 후 중앙 패널에 `Partial deliberation: claude only` 같은 작은 상태 표시를 남긴다.

### 항목 구조

각 agent 항목은 다음 구조를 가진다.

```text
[x] Claude ▾ sonnet
```

- `[x]`: 이번 질문 수신 여부를 정하는 checkbox다.
- `Claude`: agent 이름이며, 클릭하면 모델 선택 dropdown을 연다.
- `sonnet`: 현재 선택된 모델이다. 이름 오른쪽에 작게 표시한다.
- `▾`: dropdown 가능 상태를 나타낸다.

키보드 UX:

- `tab`: checkbox와 agent 이름 버튼 사이를 이동한다.
- `space`: checkbox focus에서는 선택/해제, agent 이름 focus에서는 dropdown open.
- `enter`: agent 이름 focus에서는 dropdown open 또는 선택 확정.
- `esc`: 열린 dropdown을 닫고 composer focus로 돌아간다.

### 모델 드롭다운

agent 이름을 누르면 해당 provider의 known model choices를 보여주는 dropdown이 열린다.

모델 후보 출처:

- 기본 후보는 [src/trinity/models.py](/home/user/workspace/Trinity/src/trinity/models.py)의 `provider_model_choices(provider)`를 사용한다.
- 현재 config의 `AgentSpec.model`이 후보 목록에 없으면 `Custom/current` 항목으로 맨 위에 보여준다.
- 사용자가 직접 입력한 custom model을 허용하려면 dropdown 마지막에 `Custom...` 항목을 둔다.

동작 정책:

| 상황 | 동작 |
| :--- | :--- |
| agent가 체크된 상태에서 모델 변경 | 이번 질문부터 선택 모델을 사용한다. |
| agent가 체크 해제된 상태에서 모델 변경 | 선택은 가능하지만 이번 질문에는 호출되지 않는다. 다음에 체크하면 해당 모델을 사용한다. |
| `All` 체크 상태에서 한 agent 모델 변경 | `All`은 유지되고, 해당 agent만 model override가 생긴다. |
| custom model 선택 | 짧은 입력 modal을 열고 값 검증 후 session override로 저장한다. |
| provider가 known choices를 제공하지 않음 | `default`와 현재 config model만 보여주고 custom 입력을 허용한다. |

모델 선택은 기본적으로 세션 단위 override다. 즉, 사용자가 dropdown에서 모델을 바꿔도 프로젝트 `trinity.config` 파일을 바로 수정하지 않는다. Settings 화면에서 명시적으로 저장할 때만 config에 기록한다.

요청 단위 override도 지원할 수 있다. `/ask claude --model opus ...`처럼 명령으로 들어온 값은 해당 요청에만 적용하고, UI selector의 세션 선택값은 바꾸지 않는다.

### 선택 규칙

| 상황 | 동작 |
| :--- | :--- |
| `All` 체크 | 현재 활성화된 모든 에이전트를 선택한다. |
| 개별 agent 체크 해제 | `All`은 자동 해제되고, 남은 agent만 대상이 된다. |
| 모든 개별 agent 해제 | 전송을 막고 `Select at least one agent.` 안내를 표시한다. |
| 비활성 agent | 체크박스 disabled, tooltip 또는 보조 텍스트로 `disabled by /agent`를 표시한다. |
| 모델 dropdown 변경 | 현재 세션의 agent model override를 갱신한다. |
| running 중 | selector와 composer를 잠그거나, 전송만 막고 현재 선택 상태는 유지한다. |
| 새 세션 | 기본값은 `All`. |
| resume | 마지막 선택 상태와 모델 override를 복원하되, 사용할 수 없는 agent는 자동 제외한다. |

### 전송 후 상태 표시

선택된 대상이 전체가 아니면 provider panel과 central agent 영역에 그 사실을 명확히 남긴다.

- 선택된 agent: `Running`
- 선택되지 않은 agent: `Skipped this turn` 또는 이전 상태 유지 + 흐린 표시
- central agent: `Round 2 · Targeted: claude, codex`

중앙 synthesis는 선택된 에이전트 응답만 기반으로 판단한다. 단, 기존 blueprint나 shared context는 계속 참조할 수 있다.

### 한 에이전트만 선택한 경우

한 에이전트만 선택하면 consensus라는 단어는 어색하다. UI 문구는 다음처럼 바꾼다.

- `Single-agent response`
- `Targeted answer from Claude`
- `No consensus required`

이 응답은 workflow에 follow-up으로 남기되, blueprint를 바로 대체하지 않는다. 사용자가 `Apply to blueprint` 또는 후속 전체 협의를 요청해야 blueprint 갱신으로 이어지는 편이 안전하다.

### 두 에이전트만 선택한 경우

두 에이전트만 선택하면 synthesis는 가능하지만 consensus 기준을 조정해야 한다.

- 두 에이전트가 같은 방향이면 `targeted consensus reached`.
- 의견이 다르면 중앙 에이전트가 차이를 요약하고, 필요하면 사용자 질문 또는 `Ask remaining agents` 액션을 제안한다.

### 권장 액션 버튼

대상 선택 응답 뒤 중앙 패널에 다음 액션을 보여준다.

- `Apply to plan`: 현재 blueprint/follow-up에 반영하도록 전체 또는 선택 agent로 재협의한다.
- `Ask all`: 같은 질문을 전체 에이전트에게 다시 보낸다.
- `Ask remaining`: 아직 묻지 않은 에이전트에게만 보낸다.
- `Continue targeted`: 현재 선택 상태를 유지한다.

## slash command 보조안

새 명령을 넣는다면 `/ask`가 가장 명확하다.

```text
/ask claude 게임 루프만 검토해줘
/ask claude,codex 이 설계의 데이터 흐름을 비교해줘
/ask all 방금 답변을 기준으로 전체 합의를 다시 봐줘
```

대안으로 `/to claude,codex`를 상태 설정 명령으로 둘 수도 있다.

```text
/to claude
다음 질문은 클로드에게만 간다.

/to all
다시 전체에게 보낸다.
```

하지만 `/to`는 숨은 상태를 만들기 쉬워서 초기 구현에는 권장하지 않는다. 첫 구현은 체크박스 UI와 `/ask` 단발 명령만 넣는 편이 안전하다.

기존 `/agent <name> on|off`는 계속 세션 설정으로 유지한다. `/agent`를 이번 질문 대상 선택에 재사용하지 않는다.

## 데이터 모델 설계

### UI 이벤트

`PromptComposer.Submitted` 자체에 agent 목록을 넣기보다는, screen이 composer 옆 selector 상태를 읽어 screen event에 포함하는 방식이 좋다.

```python
class StartScreen.Submitted(Message):
    prompt: str
    workspace_candidate: Path | None
    target_agents: tuple[str, ...]
    agent_model_overrides: dict[str, str]

class NexusScreen.FollowUpSubmitted(Message):
    text: str
    target_agents: tuple[str, ...]
    agent_model_overrides: dict[str, str]
```

`PromptComposer`는 텍스트 입력, paste summary, slash palette에 집중하고, recipient selector는 별도 widget으로 둔다.

### 새 widget

새 widget 후보:

```text
src/trinity/textual_app/widgets/agent_recipient_model_selector.py
```

역할:

- config의 active agents를 받아 checkbox 목록 생성
- all toggle 처리
- disabled agent 표시
- agent 이름 클릭 시 provider별 model dropdown 표시
- `provider_model_choices(provider)` 기반 model option 생성
- `selected_agents()` 반환
- `model_overrides()` 반환
- `set_selected_agents()`로 resume 또는 slash command 결과 반영
- `set_model_override(agent_name, model)`로 session model override 반영
- i18n label 제공

이 widget은 `PromptComposer` 안에 넣지 않는다. composer는 text input과 slash palette 책임을 유지하고, recipient/model selector는 Start/Nexus screen이 소유한다.

### workflow action

`WorkflowInputAction`에 요청 단위 agent 선택을 추가한다.

```python
target_agents: tuple[str, ...] = ()
agent_model_overrides: dict[str, str] = field(default_factory=dict)
agent_selection_mode: str = "all"  # all | targeted
```

다만 `WorkflowSession.active_agents`를 매번 덮어쓰면 이후 execution WP 분배까지 바뀔 수 있다. 따라서 다음을 분리한다.

- `WorkflowSession.active_agents`: workflow 기본 참여자, execution 분배 기준
- `WorkflowSession.last_target_agents`: 마지막 채팅 입력 대상
- `WorkflowSession.agent_model_overrides`: 현재 Textual 세션에서 선택한 agent별 모델 override
- `WorkflowInputAction.target_agents`: 이번 deliberation run에만 적용할 대상
- `WorkflowInputAction.agent_model_overrides`: 이번 deliberation run에 적용할 모델 override

### persistence

선택 대상과 모델 override는 감사와 resume UX를 위해 event로 남긴다.

```json
{
  "type": "workflow_continued",
  "instruction": "...",
  "target_agents": ["claude"],
  "agent_model_overrides": {"claude": "sonnet"},
  "targeted": true
}
```

세션 필드 후보:

```python
last_target_agents: list[str] = field(default_factory=list)
agent_model_overrides: dict[str, str] = field(default_factory=dict)
targeted_turns: list[dict[str, Any]] = field(default_factory=list)
```

초기 구현은 `last_target_agents`, `agent_model_overrides`, event payload만 넣고, 상세 히스토리 UI가 필요해질 때 `targeted_turns`를 추가해도 된다.

## orchestrator 라우팅 설계

가장 중요한 부분은 요청 단위 agent subset이다.

### 옵션 A: config projection 생성

`TextualWorkflowController._start_deliberation(prompt, target_agents=..., agent_model_overrides=...)`에서 config를 복사하고, 해당 run에 필요한 agent만 active로 남긴다. 모델 override가 있으면 복사된 `AgentSpec.model`만 바꾼다.

장점:

- 기존 `TrinityOrchestrator` 생성 구조를 크게 바꾸지 않는다.
- readiness, provider session mapping, model 설정이 기존 경로를 탄다.
- 모델 override를 `AgentSpec.model`에 반영하기 쉽다.

주의:

- `TrinityConfig`가 안전하게 복사 가능한지 확인해야 한다.
- config 파일 자체를 쓰면 안 된다. 메모리 projection이어야 한다.

### 옵션 B: orchestrator에 active_agent_names 파라미터 추가

`TrinityOrchestrator(..., active_agent_names=("claude",), agent_model_overrides={"claude": "sonnet"})`를 추가하고, `_ensure_initialized()`에서 `config.active_agents`를 필터링한다. wrapper 생성 직전에는 override가 있는 agent의 `AgentSpec.model`을 요청 단위로 교체한다.

장점:

- 의도가 명확하다.
- config 복사 부작용이 적다.
- 요청 단위 agent subset과 model override를 같은 경계에서 처리할 수 있다.

주의:

- execution/review에서도 같은 파라미터가 오용되지 않게 이름을 `deliberation_agent_names`로 좁히는 편이 낫다.

권장안은 옵션 B다.

```python
orchestrator = TrinityOrchestrator(
    self.config,
    interactive=use_tmux,
    provider_sessions=self.workflow.session.provider_sessions,
    active_agent_names=target_agents,
    agent_model_overrides=agent_model_overrides,
)
```

그리고 orchestrator 내부에서 다음처럼 필터링한다.

```python
active_agents = self.config.active_agents
if self.active_agent_names:
    active_agents = {
        name: spec
        for name, spec in active_agents.items()
        if name in self.active_agent_names
    }
active_agents = self._apply_agent_model_overrides(active_agents)
```

`_apply_agent_model_overrides()`는 원본 config를 mutate하지 않고 dataclass copy를 만들어야 한다.

## Central agent와 synthesis 정책

대상 agent가 일부일 때도 중앙 synthesis는 동작해야 한다.

필요한 조정:

- synthesis input metadata에 `target_agents`, `agent_selection_mode`를 넣는다.
- synthesis input metadata에 `agent_model_overrides`와 실제 resolved model도 넣는다.
- consensus denominator는 선택된 agent 수로 계산한다.
- 선택된 agent가 1개면 consensus text를 `single-agent` 모드로 렌더링한다.
- 선택되지 않은 agent response는 이번 round opinion에 포함하지 않는다.

중앙 에이전트는 “전체 합의”와 “부분 응답”을 구분해서 표현해야 한다.

예:

```text
Targeted answer from Claude

Claude는 서버 권위형 구조를 추천했다. 이 응답은 전체 합의가 아니며,
Codex와 Antigravity는 이번 turn에 호출되지 않았다.
```

## 화면 설계

### Nexus

구성 순서:

1. provider strip
2. action bar
3. central agent + inspector
4. recipient/model selector
5. prompt composer

recipient/model selector는 composer와 함께 화면 하단에 붙는다. 사용자가 입력창을 볼 때 항상 대상 선택과 모델 선택이 같이 보이게 한다.

예시:

```text
물어볼 대상: [x] 전체  [x] Claude ▾ sonnet  [ ] Codex ▾ default  [x] Antigravity ▾ default
Reply, refine direction, or type / for commands
```

### Start

첫 화면에서는 prompt composer 아래, workspace action 위에 recipient/model selector를 둔다.

```text
What should Trinity work on?
[x] All  [x] Claude ▾ sonnet  [x] Codex ▾ default  [x] Antigravity ▾ default
Target workspace: Not selected     Choose now   Plan first
```

초기 기본값은 전체 선택이며, 모델은 현재 config의 `AgentSpec.model`을 따른다.

### 모델 dropdown 시각 규칙

- dropdown은 화면 중앙 modal이 아니라 agent 이름 아래 작은 menu 형태가 좋다.
- terminal 폭이 좁아 menu가 잘릴 경우 selector row 내부가 아니라 overlay layer로 띄운다.
- 선택 중인 모델에는 check 표시를 둔다.
- context budget 또는 model source를 알 수 있으면 오른쪽에 짧게 표시한다.

```text
Claude model
✓ sonnet        200k
  opus          200k
  default       provider default
  Custom...
```

모델명은 번역하지 않는다. `provider default`, `custom` 같은 보조 문구만 i18n 대상이다.

### Provider panel

Provider panel 자체를 checkbox로 만들지는 않는다. panel은 상태 카드이고, 입력 대상 선택은 행동 컨트롤이다. 두 역할을 섞으면 provider raw output inspection과 selection focus가 충돌할 수 있다.

대신 provider panel에는 이번 turn 대상 여부만 표시한다.

- selected + running: `Running · Enabled`
- selected + ready: `Ready · Enabled`
- not selected during targeted turn: `Skipped this turn · Enabled`

## i18n

한국어 모드에서는 다음 문구를 번역한다.

| Key | English | Korean |
| :--- | :--- | :--- |
| `recipient_label` | Ask | 물어볼 대상 |
| `recipient_all` | All | 전체 |
| `recipient_none_error` | Select at least one agent. | 에이전트를 하나 이상 선택하세요. |
| `recipient_targeted` | Targeted | 선택 대상 |
| `recipient_skipped` | Skipped this turn | 이번 질문 제외 |
| `recipient_single_response` | Single-agent response | 단일 에이전트 응답 |
| `recipient_model_menu` | Model | 모델 |
| `recipient_custom_model` | Custom... | 직접 입력... |
| `recipient_provider_default` | provider default | 제공자 기본값 |

에이전트 이름, provider 이름, 모델 이름은 번역하지 않는다.

## 구현 순서

1. `AgentRecipientModelSelector` widget 추가
   - all toggle, 개별 checkbox, disabled 상태, 선택 반환 API 구현
   - agent 이름 버튼과 provider별 model dropdown 구현
   - model override 반환 API 구현
   - Textual unit test 추가
2. Start/Nexus 화면에 selector 배치
   - `StartScreen.Submitted`, `NexusScreen.FollowUpSubmitted`에 `target_agents` 추가
   - `agent_model_overrides` 추가
   - selector가 빈 선택이면 제출 차단
3. `TextualWorkflowController` API 확장
   - `start_prompt(..., target_agents=(), agent_model_overrides=None)`
   - `submit_follow_up(..., target_agents=(), agent_model_overrides=None)`
   - `_start_deliberation(prompt, target_agents=(), agent_model_overrides=None)`
4. `WorkflowEngine`에 요청 단위 selection 기록
   - session 기본 active agents와 이번 turn target agents를 분리
   - session model override와 이번 turn model override를 분리
   - `workflow_started`, `workflow_continued` event payload에 target agents와 model overrides 저장
5. `TrinityOrchestrator`에 deliberation agent subset/model override 지원
   - provider session mapping은 선택된 agent에만 전달
   - readiness check도 선택된 agent에만 수행
   - wrapper 생성 시 원본 config를 mutate하지 않고 override model 적용
6. Snapshot/UI projection 보강
   - last targeted agents 표시
   - session model override 표시
   - provider panel의 `Skipped this turn` 상태 표시
   - central agent heading에 targeted/single-agent 모드 표시
7. `/ask` 보조 command 추가
   - registry, palette description, Korean summary 추가
   - `/ask all`, `/ask claude`, `/ask claude,codex` 파싱
   - `/ask claude --model sonnet ...` 파싱
8. 회귀 테스트
   - all selected는 기존 동작과 동일
   - one agent selected는 해당 provider만 호출
   - disabled agent는 선택 불가
   - agent 이름 dropdown에서 모델을 바꾸면 해당 provider invocation에 반영
   - 모델 dropdown 변경은 config 파일을 수정하지 않음
   - slash command 입력은 recipient selector와 무관하게 local router로 처리
   - resume 후 마지막 선택 상태와 모델 override 복원

## 테스트 기준

- Start에서 `Claude`만 선택하고 prompt 제출 시 `WorkflowSession.active_agents`는 기본 전체를 유지하되, 첫 deliberation run은 Claude만 호출한다.
- Nexus에서 `Codex`만 선택하고 follow-up 제출 시 Codex provider panel만 running이 된다.
- 선택되지 않은 provider는 이번 turn에 provider invocation event가 없어야 한다.
- provider session id는 선택된 agent만 갱신되고, 선택되지 않은 agent의 session id는 유지된다.
- `/agent codex off` 후 selector에서 Codex는 disabled로 보인다.
- `/ask claude,codex ...`는 selector 클릭 없이 동일한 targeted run을 만든다.
- Start와 Nexus 모두 같은 checkbox/model dropdown UI를 보여준다.
- agent 이름을 누르면 해당 provider의 model dropdown이 열린다.
- dropdown에서 선택한 모델은 다음 provider invocation의 `AgentSpec.model` 또는 `PromptRequest.model`로 반영된다.
- dropdown에서 선택한 모델은 Settings 저장 전까지 `trinity.config`에 기록되지 않는다.
- 한국어 모드에서 selector label과 error/help 문구가 한국어로 표시된다.
- 기존 `/agent` 명령 의미는 변경되지 않는다.

## 위험과 대응

| 위험 | 대응 |
| :--- | :--- |
| session active agents를 덮어써 execution WP owner가 바뀜 | 요청 단위 target agents와 workflow 기본 active agents를 분리한다. |
| 한 agent 응답이 전체 합의처럼 보임 | central view에 `single-agent response` 또는 `targeted` 표시를 강제한다. |
| selector 상태가 숨은 전역 상태가 됨 | UI에 항상 보이는 체크박스로 유지하고, `/to` 같은 지속 상태 명령은 초기 구현에서 제외한다. |
| provider session mapping이 꼬임 | 선택된 agent만 provider session을 갱신하고, event에 target agents를 기록한다. |
| 모델 dropdown이 config를 예상치 못하게 바꿈 | dropdown은 session override만 변경하고, 파일 저장은 Settings에서만 수행한다. |
| 모델 override와 실제 provider observed model이 다름 | snapshot에 configured/actual model을 같이 보여주고 inspector에서 차이를 확인하게 한다. |
| 좁은 터미널에서 체크박스가 잘림 | selector를 wrap 가능한 grid/flex로 만들고, composer와 별도 height를 확보한다. |
| dropdown이 prompt palette와 겹침 | model dropdown과 slash palette의 z-order/focus 우선순위를 분리하고, 하나가 열리면 다른 하나는 닫는다. |
| slash command와 일반 prompt가 충돌 | `/`로 시작하는 입력은 기존처럼 local slash router가 먼저 처리한다. `/ask`만 예외적으로 provider 호출 가능 command로 등록한다. |

## 구현 범위 제안

1차 구현은 Start와 Nexus 양쪽에 같은 checkbox/model dropdown UI를 넣는다.

- 이유: 첫 prompt부터 사용자가 agent/model 조합을 고를 수 있어야 화면 간 mental model이 일관된다.
- 두 화면이 같은 widget을 공유하면 Start/Nexus의 UI 차이로 생기는 회귀를 줄일 수 있다.
- `/ask`도 1차에 같이 넣으면 테스트 자동화와 keyboard UX가 좋아진다.

2차 구현에서는 targeted response action buttons와 Settings 저장 연계를 붙인다.

이 순서가 화면 흔들림과 workflow state 부작용을 가장 작게 만든다.
