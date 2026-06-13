# Trinity 하네스 설계 관점 분석 보고서

작성일: 2026-06-12

브랜치: `feature/current-workflow-operation-analysis`

기준 문서: `docs/plans/2026-06-12-current-workflow-operation-analysis.md`

기준 소스: Trinity `0.12.9`

## 목적

이 보고서는 현재 Trinity workflow를 하네스 설계 관점에서 분석한다. 여기서 하네스는
단순 테스트 코드 묶음이 아니라, 외부 provider CLI, 상태 머신, 실행 artifact, Textual UI
projection, resume/retry, memory compact를 결정적으로 재현하고 검증하는 실행 장치다.

다음 단계에서 성능개선 사항을 분석할 예정이므로, 이 문서는 먼저 "어디를 감싸야 하는가",
"어떤 불변조건을 검증해야 하는가", "현재 테스트와 관측성에서 무엇이 부족한가"를 정리한다.

## 결론 요약

현재 Trinity는 기능 면에서 꽤 복잡한 닫힌 루프를 갖고 있다.

```text
prompt
  -> selected agent/model
  -> provider deliberation
  -> central synthesis
  -> question or blueprint
  -> execute preflight
  -> WP execution
  -> all non-owner reviews
  -> repair loop
  -> final review
  -> supplemental WP
  -> resume / execute-retry
```

따라서 하네스도 단위 테스트 중심으로는 부족하다. 특히 아래 5개 축이 필요하다.

1. Provider CLI contract harness
2. Workflow state-machine scenario harness
3. Artifact/replay harness
4. Textual snapshot/UI projection harness
5. Performance and latency harness

현재 코드에는 이미 fake CLI와 fake orchestrator를 사용하는 테스트가 일부 있다. 하지만
각 기능별 회귀 테스트로 흩어져 있고, 한 workflow run 전체를 trace로 재현하며 session,
artifact, event, UI snapshot을 동시에 검증하는 통합 하네스는 아직 부족하다.

가장 시급한 하네스 대상은 다음이다.

- provider session 지속성이 lane별로 맞는지 검증
- target agent/model 선택이 질문 답변, blueprint 보강, review 이후에도 유지되는지 검증
- 실행 중간 WP 결과가 session/report/UI에 언제 반영되는지 검증
- fallback 원인이 사용자에게 추적 가능하게 남는지 검증
- 한국어/영어 provider 출력이 같은 parser contract로 안정적으로 정규화되는지 검증
- active agent가 WP owner/reviewer로 어떤 방식으로 포함되는지 검증
- resume 후 `/context`, `/execute-retry`, snapshot load가 대형 session에서도 느려지지 않는지 측정

## 하네스 관점의 현재 구조

### 1. 설정과 provider 선택

`TrinityConfig`는 project/state directory, transport mode, provider state mode, language,
deliberation timeout, execution timeout, context/memory limit, repair retry limit, active
agent 목록을 들고 있다.

중요한 설정 경계:

- `transport_mode`: `one-shot` 또는 `tmux`
- `provider_state_mode`: `user-home` 또는 `isolated`
- `synthesis_mode`: `auto`, `model`, `heuristic`
- `synthesis_agent`, `synthesis_model`
- `memory_prompt_budget_tokens`, `shared_max_bytes`, `shared_section_entry_max_chars`
- `repair_max_attempts`

하네스는 이 값들을 fixture로 명시적으로 고정해야 한다. 특히 `one-shot`과 `tmux`는
테스트 안정성이 완전히 다르므로, 기본 scenario harness는 `one-shot + fake CLI`를 사용하고
tmux는 별도 smoke로 분리하는 것이 맞다.

근거 파일:

- `src/trinity/config.py`
- `src/trinity/models.py`
- `tests/test_setup_wizard.py`
- `tests/test_provider_model_discovery.py`

### 2. Textual controller와 background worker

Textual runtime은 `TextualWorkflowController`가 UI 이벤트를 workflow engine과 orchestrator로
연결한다.

핵심 특징:

- `start_prompt()`는 workflow를 만들고 `_start_deliberation()` background thread를 시작한다.
- `submit_follow_up()`은 현재 workflow state에 따라 질문 답변, blueprint continuation,
  post-review follow-up으로 분기한다.
- `request_execution()`은 target workspace preflight 이후 `_start_execution()`으로 간다.
- `request_review()`는 WP review와 final review를 시작한다.
- `drain_updates()`가 background thread 완료와 runtime events를 session에 반영한다.

하네스 관점에서 가장 중요한 지점은 `drain_updates()`다. 현재 execution result는 background
execution이 완전히 끝난 뒤 `record_execution_results()`로 session에 기록된다. 반면 runtime
event의 `WORK_PACKAGE_COMPLETED`는 summary 중심으로만 반영된다. 이 구조는 장시간 실행 중
"작업 보고서가 아직 보이지 않는" 현상을 만들 수 있다.

하네스 요구:

- background thread 종료 전/후 snapshot 차이를 검증한다.
- `WORK_PACKAGE_COMPLETED` 이벤트만 들어온 상태에서 UI가 무엇을 보여야 하는지 contract를
  고정한다.
- partial result를 보여주기로 결정한다면, event payload와 persisted result의 차이를 검증한다.

근거 파일:

- `src/trinity/textual_app/workflow_controller.py`
- `src/trinity/textual_app/snapshot.py`
- `tests/test_textual_workflow_controller.py`

### 3. Workflow state model

`WorkflowSession`은 하나의 Trinity workflow에 필요한 대부분의 runtime truth를 저장한다.

핵심 필드:

- `id`, `goal`, `state`, `current_round`
- `active_agents`
- `last_target_agents`
- `agent_model_overrides`
- `target_workspace`
- `pending_questions`
- `blueprint`
- `work_packages`
- `execution_results`
- `review_packages`
- `review_results`
- `post_review_items`
- `execution_run`
- `provider_sessions`
- `runtime_models`
- `resource_projections`

하네스는 session JSON을 단순 스냅샷으로만 보지 말고, 상태 전이마다 불변조건을 검사해야 한다.

필수 불변조건 후보:

- `state=needs_user_decision`이면 open question이 최소 하나 있다.
- `state=blueprint_ready`이면 blueprint가 존재한다.
- `state=executing`이면 execution_run이 running이고 target_workspace가 존재한다.
- `state=reviewing`이면 completed WP에 대한 review package가 계획되어 있다.
- `state=post_review_ready`이면 final review 또는 post_review_items가 존재한다.
- `last_target_agents`는 active agent의 부분집합이어야 한다.
- `agent_model_overrides`는 selected agent에 대해서만 유지되어야 한다.
- `provider_sessions`의 worker session과 `central:<agent>` session은 충돌하지 않아야 한다.

근거 파일:

- `src/trinity/workflow/models.py`
- `src/trinity/workflow/engine.py`
- `src/trinity/workflow/persistence.py`
- `tests/test_workflow_engine.py`
- `tests/test_workflow_persistence.py`

### 4. Provider CLI invocation

Provider 호출은 `AgentWrapper._prompt_request()`가 `PromptRequest`를 만들고, 각 provider
invoker가 실제 argv와 parser를 담당한다.

현재 호출 계약:

| Provider | 기본 호출 | 세션 지속성 | 모델 지정 |
| --- | --- | --- | --- |
| Claude | `claude -p --output-format json` | `--resume <session_id>` | `--model <model>` |
| Codex | `codex exec --json` | `codex exec resume <thread_id>` | `--model <model>` |
| Antigravity | `agy --print` | `--conversation <conversation_id>` | `--model <model>` |

Codex는 `continuity_enabled`, `provider_session_id`, `access=read-only`일 때만 `exec resume`을
쓴다. workspace-write에서는 sandbox/cwd 기반 신규 실행 성격이 강하다. 이 정책은 안전하지만,
사용자 관점에서는 "같은 에이전트 세션이 이어지는가"가 lane별로 다르므로 UI/문서/하네스에서
분명히 구분해야 한다.

주의할 점:

- 이 표는 현재 코드의 호출 의도를 설명하는 보조 자료다.
- provider CLI 플래그는 외부 CLI 버전과 Trinity invoker 변경에 따라 바뀔 수 있으므로 문서의
  문자열을 진실로 두면 안 된다.
- 하네스의 authoritative source는 `PromptRequest`를 넣었을 때 각 invoker가 만든 argv와 parser
  결과다.
- 따라서 provider별 command contract는 문서 유지가 아니라 `tests/test_provider_invoker_*.py`
  또는 표준 harness assertion으로 고정한다.

하네스 요구:

- argv contract를 provider별로 고정한다.
- read-only resume과 workspace-write execution의 명령 차이를 검증한다.
- provider stdout/stderr parser가 session id, model, usage, diagnostics를 추출하는지 검증한다.
- 실제 CLI가 실패한 경우 `response_status`, diagnostics, fallback reason이 session/report까지
  이어지는지 검증한다.

근거 파일:

- `src/trinity/agents/base.py`
- `src/trinity/agents/claude_agent.py`
- `src/trinity/agents/codex_agent.py`
- `src/trinity/agents/antigravity_agent.py`
- `src/trinity/providers/invoker.py`
- `tests/test_provider_invoker_claude.py`
- `tests/test_provider_invoker_codex.py`
- `tests/test_provider_invoker_antigravity.py`
- `tests/test_question_answer_target_e2e.py`

### 5. Deliberation and central synthesis

`DeliberationProtocol.run()`은 round별로 agent opinion을 모으고, response artifact를 쓰고,
central synthesis를 실행한다. Provider response body는 `shared.md`에 전부 쓰지 않고 artifact
path 중심으로 기록한다.

중앙 synthesis는 worker agent와 별도 logical owner를 사용한다.

```text
central:codex
central:claude
central:antigravity
```

하네스 요구:

- worker provider session과 central provider session이 서로 다른 key로 저장되는지 검증한다.
- central synthesis fallback이 발생하면 source/fallback_reason이 snapshot/report에 보이는지 검증한다.
- `next_round_prompt`가 현재는 shared context에 남지만 다음 round의 최상위 지시문으로 승격되지
  않는 제약을 회귀 테스트로 고정하거나 개선 요구로 분리한다.
- unusable provider response가 consensus denominator에서 빠지는지 검증한다.

근거 파일:

- `src/trinity/deliberation/protocol.py`
- `src/trinity/deliberation/synthesis.py`
- `src/trinity/orchestrator.py`
- `tests/test_synthesis_agent.py`
- `tests/test_deliberation_protocol_events.py`
- `tests/test_consensus_v2.py`

### 6. Execution protocol

`ExecutionProtocol`은 dependency-ready WP를 batch로 묶고 owner agent에게 workspace-write
prompt를 보낸다. 실패 또는 blocked이면 deterministic fallback order를 사용한다.

현재 fallback 우선순위:

```text
codex -> claude -> antigravity
```

중요한 동작:

- target workspace가 없거나 Trinity control repo write가 확인되지 않으면 실행 차단
- package owner 또는 last executor를 우선 시도
- 실패/blocked이면 다음 agent로 fallback
- raw execution response를 `.trinity/execution/<WP>/<agent>-<request>.raw.txt`에 기록
- markdown heading 기반으로 summary/files/decisions/blockers/follow-up/subtasks를 파싱

최근 관찰된 문제와 연결되는 하네스 포인트:

- provider가 한국어 heading으로 "완료됨", "변경된 파일", "차단 요소" 등을 쓰면 현재 parser가
  영어 heading보다 약하다.
- environment blocker pattern이 sandbox, EPERM, loopback bind 같은 검증 제한을 충분히
  구분하지 못하면 실제 구현 완료도 `blocked`로 분류되어 fallback될 수 있다.
- fallback 성공 후에도 원 시도 agent의 실패 이유와 raw artifact가 UI/report에서 충분히
  드러나야 한다.

하네스 요구:

- owner success, owner failed fallback success, owner blocked fallback success를 모두 재현한다.
- fallback attempt chain을 session/event/report에서 검증한다.
  `codex/p2-p3-scalability-hardening`에서 owner blocked -> fallback success 단위 테스트와
  session/event/report/snapshot projection 저장 경로를 추가했다. 실제 provider CLI fixture와
  한국어 heading fixture는 별도 하네스 보강 과제로 남는다.
- 영어/한국어 execution report fixture를 모두 파싱한다.
- environment-only verification blocker는 `needs_review`와 `blocked` 중 어떤 정책인지 명확히
  고정한다.
- running 중인 WP의 partial report visibility contract를 고정한다.

근거 파일:

- `src/trinity/workflow/execution.py`
- `src/trinity/providers/policy.py`
- `tests/test_execution_protocol.py`
- `tests/test_parallel_execution_policy.py`
- `tests/test_lifecycle_guard.py`

### 7. Review and repair loop

WP review는 각 완료 WP에 대해 owner/executor가 아닌 모든 active agent에게 review package를
만든다. Final review는 프로젝트 전체를 대상으로 codex -> claude -> antigravity fallback을
사용한다.

하네스 요구:

- active agent 3개, WP owner 1개일 때 review package 2개가 생기는지 검증한다.
- 한 reviewer만 approve하고 다른 reviewer가 pending이면 WP review aggregate가 approved가
  아니어야 한다.
- changes requested가 있으면 원 executor가 repair를 수행하는지 검증한다.
- 동일 required changes 반복과 max attempts 초과가 repair_blocked로 전환되는지 검증한다.
- final review의 required bugfix/validation이 supplemental `WP-S###`로 queue되는지 검증한다.

근거 파일:

- `src/trinity/workflow/review.py`
- `src/trinity/workflow/review_execution.py`
- `src/trinity/workflow/engine.py`
- `tests/test_peer_review.py`
- `tests/test_review_execution_protocol.py`
- `tests/test_textual_workflow_controller.py`

### 8. Snapshot and UI projection

Textual UI는 session/event/shared context를 직접 보여주는 것이 아니라 `NexusSnapshotAdapter`가
만든 projection을 보여준다. 따라서 하네스는 persisted truth와 UI projection이 같은 사실을
말하는지 따로 검증해야 한다.

하네스 요구:

- provider card status가 recent event와 session metadata를 올바르게 fold하는지 검증한다.
- unchecked/untargeted agent가 running으로 표시되지 않는지 검증한다.
- execution matrix의 owner/current executor/last executor/fallback label이 실제 session과
  일치하는지 검증한다.
- inspector/report가 raw JSON과 긴 텍스트를 줄바꿈/formatting하는지 snapshot으로 검증한다.
- `/model`, `/execute-retry`, `/resume` modal은 keyboard/mouse/select/scroll 동작을 Textual
  pilot 기반으로 검증한다.

근거 파일:

- `src/trinity/textual_app/snapshot.py`
- `src/trinity/textual_app/screens/nexus.py`
- `src/trinity/textual_app/screens/execution_matrix.py`
- `src/trinity/textual_app/widgets/*`
- `tests/test_textual_snapshot.py`
- `tests/test_textual_smoke.py`
- `tests/test_central_agent_view.py`

### 9. Context and memory projection

`shared.md`는 원본 provider response body를 무한히 누적하지 않고 artifact reference와 bounded
section을 유지한다. Memory index와 packer는 provider prompt에 넣을 context를 제한한다.

하네스 요구:

- `shared.md`가 threshold를 넘었을 때 oversized notice 또는 compact projection이 일관적인지 검증한다.
- `ContextPacker`가 pinned sections와 recent memory record를 budget 안에서 packing하는지 검증한다.
- `/memory compact` 이후 workflow/session/report reconstruction이 깨지지 않는지 검증한다.
- 대형 event/session/history 상태에서 snapshot load와 resume picker latency를 측정한다.

근거 파일:

- `src/trinity/context/shared.py`
- `src/trinity/context/memory.py`
- `src/trinity/context/packing.py`
- `src/trinity/context/compressor.py`
- `tests/test_shared_context.py`
- `tests/test_context_memory.py`
- `tests/test_context_packing.py`
- `tests/test_compressor.py`

## 현재 테스트 자산 평가

현재 테스트는 수량과 범위 면에서 이미 꽤 넓다.

강점:

- provider invoker 단위 테스트가 있다.
- execution protocol과 workspace guard 테스트가 있다.
- Textual workflow controller fake orchestrator 테스트가 있다.
- targeted question-answer E2E가 fake CLI를 생성해 실제 subprocess argv/stdin을 검증한다.
- peer review, review execution, model discovery, persistence, shared context 테스트가 있다.

부족한 점:

- 하나의 workflow run을 "trace"로 정의하고 session/event/artifact/snapshot/report를 함께 검증하는
  표준 scenario harness가 없다.
- fake CLI script 생성 코드가 테스트마다 흩어질 가능성이 있다.
- provider 실패, timeout, malformed output, auth required, sandbox blocked 같은 실패 injection이
  통합 matrix로 관리되지 않는다.
- 한국어 출력 contract와 영어 출력 contract가 parser 단에서 같은 수준으로 검증되지 않는다.
- execution 중간 상태의 report visibility가 명확히 고정되어 있지 않다.
- 대형 session에서 resume, execute-retry, snapshot, report 렌더링 성능을 재는 benchmark harness가 없다.
- 실제 CLI live smoke와 deterministic fake CLI test의 역할 구분이 문서화되어 있지 않다.

## 권장 하네스 아키텍처

### 디렉터리 제안

```text
tests/harness/
  __init__.py
  fake_cli.py
  scenario.py
  probes.py
  assertions.py
  fixtures.py
  traces/
    targeted_question_answer.json
    execution_fallback.json
    review_repair_loop.json
    final_review_replan.json
    resume_retry_large_session.json
```

### 핵심 구성요소

#### `FakeProviderCLI`

provider별 fake executable을 생성한다.

필요 기능:

- argv 기록
- stdin 또는 prompt argument 기록
- returncode 지정
- stdout/stderr fixture 지정
- delay/timeout simulation
- provider session id emission
- model/runtime metadata emission
- antigravity log-file emission

검증 대상:

- 실제 CLI argv가 의도와 같은지
- model override가 들어갔는지
- read-only resume argv가 들어갔는지
- workspace-write lane에서 sandbox/cwd가 들어갔는지

#### `WorkflowScenarioRunner`

Textual controller를 직접 drive한다.

필요 기능:

- start prompt
- answer question
- submit follow-up
- choose target workspace
- request execution
- request review
- execute retry
- resume archive
- drain until idle
- capture session/events/shared/snapshot/report

검증 대상:

- state transition
- session persistence
- events JSONL
- raw artifact 생성
- snapshot projection

#### `WorkflowProbe`

session과 events를 읽어 불변조건을 검사한다.

필요 기능:

- `assert_state(expected)`
- `assert_round(n)`
- `assert_provider_session(agent, lane, exists=True)`
- `assert_central_session(agent)`
- `assert_target_agents([...])`
- `assert_model_override(agent, model)`
- `assert_wp_status(wp, status)`
- `assert_execution_attempts(wp, [...])`
- `assert_reviewers(wp, [...])`
- `assert_final_review(status)`
- `assert_supplemental_wp(kind)`

#### `SnapshotProbe`

UI projection의 의미를 검증한다.

필요 기능:

- provider card status 검증
- execution matrix row 검증
- central blueprint body 검증
- question button/options 검증
- inspector/report content 검증
- retry modal candidate 검증

#### `PerformanceProbe`

대형 session fixture를 만들고 주요 operation time을 측정한다.

측정 대상:

- app startup config load
- model discovery cached/uncached
- snapshot load
- resume archive listing
- execution retry plan build
- report export
- shared.md read/compact
- memory pack

## 핵심 scenario matrix

| ID | Scenario | 목적 | 필수 검증 |
| --- | --- | --- | --- |
| H-001 | all agents -> central question -> answer -> blueprint | 기본 workflow | round=1, question 생성, 답변 후 blueprint |
| H-002 | Codex only + model override -> answer | 대상 유지 | target_agents와 model override 유지, 다른 provider 미호출 |
| H-003 | central synthesis provider session | 중앙 세션 분리 | `central:codex` session이 worker codex와 분리 |
| H-004 | owner blocked -> fallback success | fallback 추적 | attempt chain, raw artifact, fallback label, reason |
| H-005 | long execution partial report | 실행 중 보고 | WP completed event 후 UI/report 표시 contract |
| H-006 | Korean execution report | parser 다국어 | files/blockers/decisions/follow-up 파싱 |
| H-007 | all non-owner reviews | 리뷰 분배 | WP owner 제외 모든 active agent review |
| H-008 | repair loop duplicate guard | repair 안정성 | 원 executor 재시도, duplicate/max attempts block |
| H-009 | final review auto replan | 보강 WP | required bugfix/validation -> `WP-S###` |
| H-010 | resume + context + execute-retry | 복구 UX | resume 직후 snapshot/context, retry modal candidates |
| H-011 | model discovery modal | 실제/캐시 모델 | CLI live 결과, fallback, selected row 유지 |
| H-012 | large session performance | 렉 방지 | snapshot/resume/retry/report latency budget |

1차 구현 범위:

- H-004 fallback trace
- H-005 partial report visibility
- H-007/H-008 review and repair loop
- H-010 resume, context, execute-retry
- H-012 large session performance

나머지 H-001/H-003 기본 흐름은 기존 테스트 자산을 표준 harness로 옮기는 성격이 강하다. 따라서
초기 PR에서는 최근 실제 장애와 직접 연결된 scenario를 먼저 고정하고, baseline happy path는
하네스 골격이 안정된 뒤 편입한다.

## 불변조건 상세

### State-machine invariants

- `idle`은 의미 있는 session data가 없어야 한다.
- `deliberating`은 background deliberation thread 또는 방금 완료된 result pending과 연결되어야 한다.
- `needs_user_decision`은 open question이 있어야 한다.
- `blueprint_ready`는 blueprint가 있어야 한다.
- `executing`은 target workspace와 execution_run이 있어야 한다.
- `reviewing`은 completed WP review, repair review, pending final review, supplemental review 중
  하나의 명확한 review work와 연결되어야 한다.
- `done`은 executable WP와 required review가 모두 완료되어야 한다.
- `failed`는 failure reason event가 있어야 한다.

### Provider/session invariants

- provider session key는 provider, agent_name, lane, access, cwd hash, model을 포함해야 한다.
- central synthesis session은 `central:<agent>` logical owner를 사용해야 한다.
- read-only continuity는 provider별 resume flag를 사용해야 한다.
- workspace-write execution은 현재 정책상 read-only session과 분리된다. 이 정책을 유지한다면
  harness는 "resume되지 않는 것"도 명시적으로 검증해야 한다.
- runtime model confidence가 `unknown`이면 UI/report에서 확정 정보처럼 표현하면 안 된다.

### Execution invariants

- target workspace 없이 workspace-write가 발생하면 안 된다.
- Trinity control repo write는 명시 확인 없이는 차단되어야 한다.
- `running` WP는 `current_executor`가 있어야 한다.
- `done/failed/blocked` WP는 `current_executor`가 비어 있고 `last_executor`가 있어야 한다.
- fallback이 발생하면 owner와 last_executor가 다를 수 있으며, UI가 이를 표시해야 한다.
- completed WP마다 raw_response_path가 있어야 한다.
- parser가 이해하지 못한 provider output은 raw artifact로 추적 가능해야 한다.

### Review invariants

- active agent가 2개 이상이면 self-review는 기본적으로 없어야 한다.
- completed WP마다 non-owner reviewer package가 모두 있어야 한다.
- 모든 planned review가 완료되기 전에는 aggregate approved가 되면 안 된다.
- repair는 original executor 또는 last executor로 돌아가야 한다.
- duplicate repair와 max attempts 초과는 blocked로 전환되어야 한다.
- final review는 WP review approve 이후에만 실행되어야 한다.

### Snapshot/report invariants

- snapshot은 session truth와 모순되면 안 된다.
- report는 completed execution/review raw artifact를 추적할 수 있어야 한다.
- 실행 중 partial state와 완료 후 final state를 구분해 보여야 한다.
- inspector는 긴 텍스트와 JSON을 줄바꿈/pretty format해야 한다.
- provider status는 선택되지 않은 agent를 running으로 표시하면 안 된다.

## 최근 증상에 대한 하네스 해석

### 작업보고서가 바로 보이지 않는 문제

현재 엔진에는 `record_execution_results(..., finalize=False)`로 실행 중간 결과를 session에
upsert하는 경로가 있다. 따라서 문제를 "partial persist 기능이 전혀 없다"로 보면 안 된다.

실제 회귀 위험은 다음 계약이 화면과 report까지 일관되게 고정되어 있지 않다는 점이다.

- execution worker가 WP 완료 시점마다 partial result를 전달하는가
- session에는 `finalize=False`로 upsert되지만 state는 `executing`을 유지하는가
- events에는 중복 없이 완료/요약/attempt chain이 남는가
- Nexus/Execution/Report snapshot이 실행 종료 전 partial result를 표시하는가

하네스 대응:

- H-005에서 WP-001 완료, WP-002 running 상태를 만든다.
- session, events, snapshot, report가 각각 어떤 내용을 보여야 하는지 고정한다.
- product decision이 "partial report 표시"라면 `WORK_PACKAGE_COMPLETED` event에 raw artifact
  path 또는 parsed partial result를 포함하도록 요구한다.

### Codex fallback 원인 추적 문제

Codex가 실제 구현을 했더라도 output의 blockers가 environment verification blocker로 분류되지
않으면 `blocked`가 되고 fallback이 발생한다. 이때 다음 agent가 성공하면 Execution Matrix에는
`claude fallback`처럼 보이지만, 왜 Codex가 fallback되었는지 사용자가 바로 알기 어렵다.

하네스 대응:

- H-004에서 Codex output에 `EPERM`, `loopback bind`, `sandbox` blocker를 넣는다.
- 정책에 따라 `needs_review` 또는 `blocked`가 되는지 검증한다.
- fallback reason과 original raw artifact가 UI/report에 노출되는지 검증한다.
  현재 구현은 `ExecutionResult.attempt_chain`에 agent/status/summary/blockers/raw_response_path를
  저장하고, Work Package detail modal과 Deliberation Report markdown에 노출한다.

### Antigravity가 WP owner로 배정되지 않는 문제

현재 decomposer는 중앙 blueprint가 명시한 owner를 보존한다. 선택된 active agent 모두에게 WP를
최소 하나씩 배정하는 fairness invariant는 없다. 따라서 Antigravity가 deliberation에 참여해도
중앙 blueprint가 owner를 Codex/Claude만 지정하면 WP 목록에 Antigravity owner가 없을 수 있다.

하네스 대응:

- active agent 3개, 중앙 blueprint owner 2개만 있는 fixture를 만든다.
- 현재 동작을 고정할지, active agent coverage를 요구할지 product decision을 분리한다.
- coverage를 요구한다면 validation/risk WP는 Antigravity에 backfill하는 decomposer policy를
  추가하고 regression으로 고정한다.

## 성능개선 분석을 위한 측정 포인트

다음 작업에서 성능개선을 분석하려면 먼저 측정 지점을 정해야 한다.

### Latency metrics

| Metric | 위치 | 의미 |
| --- | --- | --- |
| `startup.config_load_ms` | CLI/Textual app start | config/model/cache load 비용 |
| `model_discovery.live_ms` | `/model` modal | provider CLI 모델 목록 조회 비용 |
| `model_discovery.cached_ms` | `/model` modal | cache hit 비용 |
| `snapshot.load_ms` | `NexusSnapshotAdapter.load_snapshot()` | Nexus 렌더링 전 projection 비용 |
| `events.load_ms` | `WorkflowPersistence.load_events()` | events JSONL tail 비용 |
| `resume.list_ms` | `WorkflowPersistence.list_archives()` | resume modal 비용 |
| `execute_retry.plan_ms` | `build_execution_retry_plan()` | retry modal 비용 |
| `report.export_ms` | report screen/export | 보고서 렌더링 비용 |
| `shared.read_ms` | `SharedContextEngine.read()` | shared.md read 비용 |
| `memory.pack_ms` | `ContextPacker.pack()` | provider prompt context 구성 비용 |

### Size metrics

| Metric | 의미 |
| --- | --- |
| `session_json_bytes` | session load/save 비용 |
| `events_jsonl_bytes` | event replay 비용 |
| `events_count` | snapshot/report fold 비용 |
| `shared_md_bytes` | shared context read/compact 비용 |
| `memory_records_count` | memory pack 후보 수 |
| `artifact_count` | report/audit reconstruction 비용 |
| `work_package_count` | execution matrix/retry planner 비용 |
| `review_result_count` | review aggregation 비용 |

### Suggested budgets

초기 목표값은 보수적으로 잡는다.

- `/resume` modal open: 150ms 이하, archive 100개에서 300ms 이하
- Nexus snapshot load: event 5,000개에서 100ms 이하
- Execution matrix render projection: WP 50개, review 150개에서 100ms 이하
- `/execute-retry` plan: WP 50개에서 50ms 이하
- `/model` cached open: 50ms 이하
- `/model` live discovery: provider별 timeout 3초, UI는 loading/partial 표시
- memory pack: record 1,000개에서 150ms 이하

## 구현 우선순위

### P0: 표준 하네스 골격

- `tests/harness/fake_cli.py` 추가
- `tests/harness/scenario.py` 추가
- session/events/shared/snapshot probe 추가
- provider별 fake CLI output fixture 통합

완료 기준:

- 새 scenario test가 fake provider CLI 3개를 만들고 one-shot workflow를 end-to-end로 돌린다.
- session JSON, events JSONL, shared.md, raw artifacts, snapshot을 한 번에 assert할 수 있다.

### P1: 현재 회귀 위험 고정

- target agent/model 유지
- provider session continuity
- central session separation
- fallback reason trace
- Korean execution parser
- all non-owner review
- final review auto replan
- resume + context + execute-retry

완료 기준:

- 최근 사용자 발견 이슈가 fixture로 재현된다.
- 버그 수정 전 실패, 수정 후 통과하는 regression이 존재한다.

### P2: Replay and report harness

- `.trinity/workflow/session.json`과 `events.jsonl` fixture replay
- raw artifacts fixture replay
- report/snapshot reconstruction 검증
- 대형 session fixture 생성기

완료 기준:

- 실제 provider CLI 없이 과거 session을 복원해 Nexus/report를 검증한다.
- report 누락, fallback reason 누락, review aggregation 오류를 deterministic하게 잡는다.

구현 상태:

- `codex/p2-p3-scalability-hardening`에서 `tests/harness/replay.py`를 추가해 persisted
  workflow session, workflow events, raw artifacts를 로드하고 `WorkflowNexusSnapshot`과
  `DeliberationReport`를 재구성한다.
- `tests/test_replay_harness.py`는 fallback attempt chain, raw artifact manifest, work package
  review aggregation, final review projection이 replay 후에도 유지되는지 검증한다.

### P3: Performance harness

- pytest benchmark가 없어도 단순 monotonic timer 기반 smoke budget을 둔다.
- 대형 session/event/shared fixture를 생성한다.
- CI에서는 느슨한 threshold, local에서는 상세 metric 출력.

완료 기준:

- resume, snapshot, execute-retry, report, memory pack의 기준값이 문서화된다.
- 성능개선 PR마다 before/after를 비교할 수 있다.

구현 상태:

- `feature/current-workflow-operation-analysis`에서 `tests/harness/perf.py`와
  `tests/test_performance_harness.py`를 추가해 session/events/shared/review 규모별 fixture와
  monotonic timer 기반 smoke probe를 만들었다.
- `codex/p2-p3-scalability-hardening`에서 replay/report harness와 P2/P3 확장성 검증을 보강해
  snapshot, report, event index, memory pack, artifact manifest가 같은 fixture 흐름에서
  검증되도록 확장했다.

### P4: Optional live smoke

실제 Claude/Codex/Antigravity CLI 호출은 deterministic CI에 넣기 어렵다. 대신 local-only smoke로
분리한다.

완료 기준:

- `TRINITY_LIVE_PROVIDER_SMOKE=1`일 때만 실제 CLI를 호출한다.
- live smoke는 모델명/session id/argv contract만 짧게 확인하고 실제 파일 변경은 하지 않는다.

## 최종 권고

Trinity의 다음 품질 단계는 "기능별 테스트 추가"보다 "workflow trace 하네스"가 먼저다.
현재 문제들은 대부분 단일 함수 버그가 아니라 다음 사이에서 발생한다.

- provider CLI output과 parser contract
- runtime event와 persisted session
- session truth와 Textual snapshot
- owner/fallback/reviewer policy와 사용자 기대
- read-only session continuity와 workspace-write execution policy
- large `.trinity` state와 UI latency

따라서 하네스는 provider를 fake로 대체하되 실제 subprocess argv/stdin/stdout/stderr 계약을
유지해야 한다. 그리고 workflow controller를 실제로 drive하면서 session, events, shared context,
artifact, snapshot, report를 동시에 검증해야 한다.

이 구조가 생기면 이후 성능개선도 감으로 하지 않고, replay fixture와 latency metric을 기준으로
"어디서 느린지", "개선 후 무엇이 빨라졌는지", "기능 회귀가 없는지"를 같은 하네스에서 확인할 수 있다.
