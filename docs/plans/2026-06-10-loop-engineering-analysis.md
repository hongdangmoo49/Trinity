# Trinity Loop Engineering 적용 분석

작성일: 2026-06-10

브랜치:

- 분석: `feature/loop-engineering-analysis`
- 1차 구현: `feature/loop-engineering-mvp`

상태: Phase 1 manual loop MVP 구현 반영

참조: [루프 엔지니어링 - 에이전트를 프롬프트하는 시스템을 설계하기](https://news.hada.io/topic?id=30336)

## 목적

Trinity를 "사용자가 매번 agent에게 직접 지시하는 도구"에서 "목표, 상태, 검증 조건을 가진
루프가 agent를 반복 호출하는 개발 시스템"으로 확장할 때 어떤 방식이 가장 적절한지 분석한다.

결론부터 말하면, Trinity에는 이미 workflow state machine, execution/review protocol,
resource overlay, shared memory, provider abstraction이 있으므로 외부 자동화 스크립트를
두껍게 붙이기보다 `LoopEngine`을 일급 orchestration layer로 추가하는 방식이 가장 적절하다.

## 참조 글의 핵심 요약

글에서 말하는 루프엔지니어링은 코딩 agent에게 매 턴 직접 프롬프트하는 방식에서 벗어나,
agent에게 무엇을 시킬지 결정하는 작은 시스템을 설계하는 방식이다. 구성 요소는 다음 여섯
가지로 정리할 수 있다.

| 요소 | 의미 | Trinity 대응 |
| :--- | :--- | :--- |
| Automations | 스케줄이나 이벤트로 루프를 깨우는 장치 | 아직 없음. CLI/manual entrypoint만 있음 |
| Worktrees | 병렬 agent 충돌을 막는 격리 작업공간 | `WorkspaceIsolation`, execution parallel policy |
| Skills | 프로젝트 지식을 추측 대신 파일로 제공 | `.trinity/resources/packs/*`, prompt inventory |
| Plugins/connectors | GitHub, Linear, Slack, CI 같은 외부 도구 연결 | 아직 core connector 없음 |
| Sub-agents | 제안자, 구현자, 검증자를 분리 | Claude/Codex/Antigravity + synthesis/review protocol |
| Memory | 대화 밖에 남는 장기 상태 | `.trinity/shared.md`, workflow session/events, memory index |

중요한 포인트는 "모델은 실행 사이에 잊고, repo와 디스크는 잊지 않는다"는 전제다. 따라서
Trinity의 루프도 provider 대화 맥락에 의존하지 않고 `.trinity` 아래의 명시적 상태를
truth source로 삼아야 한다.

## 현재 Trinity의 적합성

Trinity는 루프엔지니어링을 바로 시작하기 좋은 기반을 이미 갖고 있다.

| 현재 컴포넌트 | 이미 가능한 일 | 루프 관점의 부족한 점 |
| :--- | :--- | :--- |
| `WorkflowEngine` | 목표, 질문, 결정, blueprint, WP, 실행/리뷰 상태 저장 | 하나의 workflow를 반복 run으로 묶는 상위 run 상태가 없음 |
| `TextualWorkflowController` | planning/execution/review를 background worker로 실행 | 자동 반복과 queue 관리가 없음 |
| `TrinityOrchestrator` | provider별 agent 생성, readiness, resource projection, 실행 호출 | loop-level budget/stop policy를 모름 |
| `ExecutionProtocol` | WP dependency, 파일 충돌, workspace-write guard | loop iteration 간 diff/gate 판단은 없음 |
| `ReviewExecutionProtocol` | WP/final review를 provider로 수행 | reviewer 결과를 loop 종료 조건으로 일반화하지 않음 |
| `ResourceProjector` | Trinity-owned skill/resource를 provider turn에 제공 | loop별 skill pack 활성화 lock이 없음 |
| `SharedContextEngine` / `MemoryStore` | shared.md와 SQLite memory index | loop ledger, loop decision, next action queue가 없음 |
| `WorkspaceIsolation` | agent별 git worktree 생성 | branch 이름이 agent 기준이라 loop/run 단위 격리가 약함 |
| Slash/Textual UI | user-guided workflow 조작 | loop dashboard, pause/resume/stop surface 없음 |

즉, 부족한 것은 agent 호출 능력이 아니라 "반복을 통제하는 명시적 루프 상태"다.

분석 근거로 확인한 현재 코드와 문서는 다음이다.

| 근거 | 확인한 내용 |
| :--- | :--- |
| `src/trinity/workflow/engine.py` | workflow session, 질문/결정, blueprint, 실행/리뷰 상태 전이 |
| `src/trinity/orchestrator.py` | provider agent 생성, readiness, resource projection, execution/review 위임 |
| `src/trinity/textual_app/workflow_controller.py` | Textual에서 workflow action을 background worker로 실행하는 경계 |
| `src/trinity/workflow/execution.py` | workspace-write guard, WP dependency, 안전한 병렬 batch |
| `src/trinity/workflow/review_execution.py` | provider-backed WP/final review |
| `src/trinity/resources/*` | Trinity-owned resource pack registry와 prompt inventory projection |
| `src/trinity/context/shared.py` / `src/trinity/context/memory.py` | shared context와 SQLite memory index |
| `docs/plans/2026-06-09-agent-resource-overlay-design.md` | provider-native resource와 Trinity overlay 분리 정책 |
| `docs/plans/2026-06-09-review-repair-loop-guard-design.md` | 기존 자동 repair loop의 무한 반복 방지 경험 |
| `docs/workflow-v0.10.2-guide.md` | 현재 workflow/runtime 동작 요약 |

## 후보 방식 비교

### 1. Bash/cron wrapper 방식

`trinity ask`, `/execute`, `/review`를 shell script나 cron으로 반복 실행하는 방식이다.

장점:

- 가장 빠르게 실험할 수 있다.
- 기존 코드를 거의 건드리지 않는다.
- manual smoke loop에는 충분하다.

단점:

- workflow state와 loop state가 분리되어 실패 복구가 어렵다.
- stop condition, budget, review gate를 script가 임의로 해석하게 된다.
- Textual UI와 event log에 루프 의도가 보이지 않는다.
- provider별 실패와 사용자 승인 지점을 구조적으로 표현하기 어렵다.

판단: prototype으로는 가능하지만 Trinity의 장기 방향으로는 부적절하다.

### 2. `WorkflowEngine` 자체를 self-loop로 확장

현재 state machine에 `LOOPING`, `WAITING_TRIGGER`, `EVALUATING` 같은 상태를 직접 추가한다.

장점:

- 구현 파일 수가 적다.
- session/event persistence를 바로 재사용한다.
- Textual snapshot과 연결하기 쉽다.

단점:

- 이미 workflow 상태가 planning, execution, review, post-review를 많이 담당한다.
- "하나의 workflow 안 단계"와 "여러 workflow/iteration을 반복하는 상위 루프"가 섞인다.
- 나중에 GitHub issue triage, nightly scan처럼 workflow 하나로 끝나지 않는 루프를 표현하기 어렵다.

판단: 작게 보이지만 상태 머신이 금방 비대해진다. 추천하지 않는다.

### 3. 별도 `LoopEngine`을 `WorkflowEngine` 위에 두는 방식

`LoopEngine`이 loop spec, run, iteration, gate, memory를 관리하고, 실제 계획/실행/리뷰는
기존 `WorkflowEngine`과 `TrinityOrchestrator`에 위임한다.

장점:

- 기존 workflow 구현을 최대한 재사용한다.
- loop state와 workflow state가 분리되어 디버깅하기 쉽다.
- manual loop, scheduled loop, connector-triggered loop를 같은 모델로 담을 수 있다.
- stop/budget/gate/human approval을 provider-agnostic하게 구현할 수 있다.
- Textual에는 "현재 workflow"와 별개로 "loop run" dashboard를 올릴 수 있다.

단점:

- 새 모델과 persistence가 필요하다.
- WorkflowEngine과의 contract를 명확히 하지 않으면 중복 상태가 생긴다.
- 첫 구현 범위를 작게 자르지 않으면 커질 수 있다.

판단: Trinity에 가장 적합한 방식이다.

### 4. 외부 orchestrator 사용

Temporal, Prefect, GitHub Actions, systemd timer 같은 외부 실행기를 루프의 중심으로 둔다.

장점:

- scheduling, retry, queue, observability를 이미 갖고 있다.
- 서버/팀 운영으로 가면 안정적이다.
- GitHub Actions는 PR/CI와 잘 붙는다.

단점:

- 개인 로컬 WSL 개발 도구인 Trinity의 기본 UX와 멀어진다.
- provider auth, managed home, target workspace guard가 외부 runner와 꼬일 수 있다.
- state truth source가 `.trinity`와 외부 시스템으로 갈라진다.
- 초기 설계/테스트 비용이 크다.

판단: 나중에 connector/automation backend 중 하나로 지원할 수는 있지만 core loop engine으로는
너무 무겁다.

### 5. Agent self-loop prompt 방식

agent에게 "완료될 때까지 스스로 반복해라"라고 시키고, 사람이 결과만 보는 방식이다.

장점:

- 구현이 거의 없다.
- 특정 작은 작업에서는 빠르다.

단점:

- 무한 반복, 비용 폭주, 잘못된 완료 판정을 막기 어렵다.
- 메모리가 provider 대화 안에 갇힌다.
- reviewer와 implementer 분리가 약하다.
- 파일 변경, 테스트, PR 상태 같은 외부 증거를 루프의 truth source로 삼기 어렵다.

판단: 루프엔지니어링이라기보다 긴 프롬프트다. Trinity 방향과 맞지 않는다.

### 6. GitHub-first connector loop

GitHub issue, PR review, CI failure를 루프 입력으로 삼아 triage부터 자동화하는 방식이다.

장점:

- 실제 개발 workflow와 바로 맞닿는다.
- loop의 입력과 완료 증거가 명확하다.
- PR comment, CI status, review request를 자동화하기 좋다.

단점:

- GitHub에 과하게 종속된다.
- local-only 프로젝트와 맞지 않을 수 있다.
- connector부터 시작하면 loop core 없이 webhook 처리 코드가 먼저 커진다.

판단: 첫 connector로는 좋지만, engine보다 먼저 만들면 구조가 뒤집힌다.

## 권장안

권장 구조는 `LoopEngine`을 새 상위 계층으로 추가하고, 첫 버전은 manual trigger만 지원하는
것이다.

```text
trinity loop run <loop-id>
  -> LoopEngine.load_spec()
  -> LoopRun 생성
  -> LoopIteration 시작
  -> WorkflowEngine.start()/continue/execute/review 재사용
  -> LoopGate 평가
  -> LoopMemory 기록
  -> 다음 iteration 또는 stop
```

핵심 원칙:

1. LoopEngine은 provider를 직접 호출하지 않는다. 호출은 `WorkflowEngine`/`TrinityOrchestrator`를 통한다.
2. LoopEngine은 workflow session을 소유하지 않고 참조한다. 상위 loop run과 하위 workflow id를 연결한다.
3. 완료 판정은 agent 응답이 아니라 gate 결과로 한다.
4. 모든 반복에는 hard stop이 있어야 한다.
5. 자동화는 manual loop가 안정화된 뒤 붙인다.

## 제안 디렉터리 구조

```text
.trinity/
  loops/
    registry.toml
    specs/
      daily-triage.toml
      pr-review.toml
    runs/
      looprun-20260610-001/
        loop.json
        ledger.md
        events.jsonl
        iteration-001/
          workflow_id.txt
          gate-results.json
          artifacts/
        iteration-002/
          workflow_id.txt
          gate-results.json
          artifacts/
    queue/
      pending.jsonl
      claimed/
  workflow/
    session.json
    events.jsonl
  resources/
    packs/
```

역할:

- `specs/*.toml`: 사람이 관리하는 loop 정의다.
- `runs/*/loop.json`: 특정 실행의 현재 상태다.
- `runs/*/ledger.md`: 사람이 읽는 결정/결과/다음 행동 기록이다.
- `events.jsonl`: machine-readable append-only event log다.
- `iteration-*/workflow_id.txt`: 하위 Trinity workflow와 loop iteration을 연결한다.
- `queue/`: automation trigger가 만든 실행 요청을 저장한다.

## 핵심 데이터 모델

### LoopSpec

```python
@dataclass
class LoopSpec:
    id: str
    title: str
    goal: str
    trigger: LoopTrigger
    agents: list[str]
    resource_packs: list[str]
    target_workspace: str
    max_iterations: int
    max_runtime_seconds: int
    max_token_budget: int
    gates: list[LoopGateSpec]
    stop_policy: LoopStopPolicy
```

예시 TOML:

```toml
id = "local-quality-loop"
title = "Local Quality Loop"
goal = "현재 브랜치의 실패 테스트와 리뷰 지적을 찾아 수정하고 검증한다."
agents = ["codex", "claude", "antigravity"]
resource_packs = ["trinity-core", "review-hardening"]
target_workspace = "."
max_iterations = 3
max_runtime_seconds = 7200
max_token_budget = 250000

[trigger]
type = "manual"

[[gates]]
id = "unit-tests"
type = "command"
command = ".venv/bin/pytest -q"
required = true

[[gates]]
id = "diff-review"
type = "provider-review"
reviewer = "codex"
required = true

[stop_policy]
on_gate_pass = "complete"
on_gate_fail = "iterate"
on_budget_exceeded = "pause"
on_user_decision_required = "pause"
```

### LoopRun

```python
@dataclass
class LoopRun:
    id: str
    spec_id: str
    status: Literal["queued", "running", "paused", "complete", "failed", "cancelled"]
    iteration: int
    workflow_ids: list[str]
    started_at: float
    updated_at: float
    stop_reason: str
    token_used: int
    gate_results: list[LoopGateResult]
```

### LoopIteration

한 iteration은 다음 순서를 따른다.

```text
discover
  -> plan
  -> execute
  -> verify
  -> review
  -> persist
  -> decide_next
```

Trinity의 현재 workflow와 매핑하면 다음과 같다.

| Loop step | Trinity 재사용 |
| :--- | :--- |
| discover | connector input, git status, CI output, previous ledger |
| plan | `WorkflowEngine.start()` + `TrinityOrchestrator.ask()` |
| execute | `WorkflowEngine.enable_execution_for_current_blueprint()` + `ExecutionProtocol` |
| verify | local command gate, test result artifact |
| review | `ReviewExecutionProtocol` 또는 provider-backed gate |
| persist | loop ledger + workflow events + memory index |
| decide_next | stop policy + max iteration/budget/human gate |

## Gate 설계

Gate는 loop가 "완료"를 주장하기 전에 보는 증거다.

| Gate | 설명 | 1차 지원 여부 |
| :--- | :--- | :--- |
| command | pytest, npm test, lint 같은 로컬 명령 | 필수 |
| diff | 변경 파일 범위, forbidden path, dirty tree 검사 | 필수 |
| workflow-state | workflow가 `DONE`/`POST_REVIEW_READY`인지 확인 | 필수 |
| provider-review | reviewer agent가 승인/수정 요청을 반환 | 2차 |
| connector-status | GitHub check, PR review, issue label | connector 이후 |
| human-approval | 사용자가 승인해야 다음 단계 진행 | 필수 |

Gate 결과는 pass/fail만으로 부족하다. 다음 정보를 저장해야 한다.

```json
{
  "id": "unit-tests",
  "status": "failed",
  "summary": "3 failed, 182 passed",
  "artifact_path": ".trinity/loops/runs/.../gate-results/unit-tests.txt",
  "retryable": true,
  "blocking": true
}
```

## Automation 설계

초기에는 daemon을 만들지 않는다. 자동화는 세 단계로 나눈다.

1. Manual: `trinity loop run <id> --once`
2. Local queue: `trinity loop enqueue <id>`와 `trinity loop worker --once`
3. Scheduler/connector: cron, GitHub webhook, CI failure, idle timer

이 순서가 중요한 이유는 stop policy와 ledger가 안정화되기 전에 always-on worker를 만들면
오작동 비용이 커지기 때문이다.

## Worktree 정책

현재 `WorkspaceIsolation`은 agent 이름 기준 branch와 worktree를 만든다. 루프에는 부족하다.
loop/run/iteration을 branch 이름에 포함해야 병렬 루프가 충돌하지 않는다.

권장 branch:

```text
trinity/loop/<spec-id>/<run-id>/<agent>
```

권장 path:

```text
.trinity/loops/worktrees/<run-id>/<agent>/
```

1차 구현에서는 기존 target workspace guard를 그대로 쓰고, loop worktree는 feature flag로 둔다.
다만 설계상 branch naming은 처음부터 loop-safe하게 잡아야 한다.

## Skills와 resource pack 정책

루프에서 skill은 "agent가 추측하면 안 되는 프로젝트 지식"이다. 이미 구현된 resource overlay를
그대로 활용하되, loop spec에서 pack을 고정해야 한다.

권장:

- `resource_packs`는 loop spec에 명시한다.
- loop run 시작 시 pack checksum을 `loop.json`에 lock한다.
- iteration 중 pack이 바뀌면 다음 iteration부터 반영하거나 run을 pause한다.
- provider-native skill/hook에 직접 쓰지 않고 prompt inventory/managed overlay를 우선한다.

## Connector 정책

첫 connector는 GitHub가 가장 적합하다.

이유:

- Trinity 개발 자체가 GitHub PR 중심이다.
- issue, PR, CI, review comment는 loop input/gate로 쓰기 좋다.
- "완료" 증거가 commit, check, PR state로 남는다.

단, GitHub connector는 core가 아니라 trigger/gate adapter여야 한다.

```text
GitHub issue/PR/CI
  -> LoopTriggerEvent
  -> LoopEngine
  -> WorkflowEngine
  -> LoopGateResult
  -> GitHub comment/status update
```

## Memory 정책

루프 memory는 `shared.md` 하나로 충분하지 않다. `shared.md`는 현재 workflow의 shared brain이고,
loop는 여러 iteration과 workflow를 묶는 상위 기억이 필요하다.

권장 memory 계층:

| 계층 | 파일 | 역할 |
| :--- | :--- | :--- |
| Workflow memory | `.trinity/shared.md` | 현재 workflow agent context |
| Workflow event | `.trinity/workflow/events.jsonl` | state transition truth source |
| Loop ledger | `.trinity/loops/runs/<run>/ledger.md` | 사람이 읽는 반복 기록 |
| Loop event | `.trinity/loops/runs/<run>/events.jsonl` | machine-readable loop event |
| Memory index | `.trinity/memory/index.sqlite` | 검색/압축 가능한 artifact index |

Loop ledger에는 최소한 다음이 들어가야 한다.

- original loop goal
- iteration별 계획, 실행 요약, gate 결과
- 사용자 결정과 stop reason
- 다음 iteration에 반드시 전달할 constraints
- provider별 비용/토큰 사용량

## Sub-agent 정책

Trinity의 세 agent를 단순히 모두 같은 일을 시키는 방식보다 역할을 분리하는 편이 루프에 맞다.

권장 역할:

| 역할 | 우선 agent | 설명 |
| :--- | :--- | :--- |
| Planner | Claude 또는 Codex | 다음 iteration 계획과 risk 분석 |
| Implementer | Codex 또는 Antigravity | workspace-write 실행 |
| Reviewer | Codex -> Claude -> Antigravity fallback | diff/test/review gate |
| Judge | Central synthesis model | stop/iterate/pause 판정 |

이 역할은 provider 고정이 아니라 loop spec에서 바꿀 수 있어야 한다.

## Safety와 stop policy

루프는 반드시 유한하고 중단 가능해야 한다.

필수 hard stop:

- `max_iterations`
- `max_runtime_seconds`
- `max_token_budget`
- 동일 gate failure signature 반복 횟수
- 동일 review repair signature 반복 횟수
- target workspace 없음
- control repo write 미승인
- provider readiness 실패
- 사용자 결정 필요

기본 정책:

| 상황 | 기본 동작 |
| :--- | :--- |
| 모든 required gate 통과 | complete |
| retryable gate 실패 | 다음 iteration |
| 같은 실패가 2회 반복 | pause and ask user |
| budget 80% 도달 | warning event |
| budget 초과 | pause |
| 새 dependency 설치 필요 | pause and ask user |
| secret/auth 필요 | pause |
| control repo write 필요 | existing guard 재사용 |

## 구현 로드맵

### Phase 1: Manual Loop MVP

목표: 자동화 없이 루프 상태와 gate를 검증한다.

작업:

1. `src/trinity/loop/models.py` 추가
2. `src/trinity/loop/persistence.py` 추가
3. `src/trinity/loop/engine.py` 추가
4. CLI `trinity loop run/status/stop` 추가
5. `LoopSpec` TOML loader 추가
6. command gate와 workflow-state gate 구현
7. loop ledger/events 저장

성공 기준:

- `trinity loop run local-quality-loop --once`가 workflow를 1회 돌리고 gate 결과를 저장한다.
- 실패 gate가 있으면 `paused` 또는 `running next iteration` 중 하나로 명확히 기록된다.
- 모든 상태가 `.trinity/loops/runs/*` 아래에 남는다.

### Phase 2: Iteration 반복과 budget

작업:

1. max iteration 적용
2. 반복 실패 signature 감지
3. token/runtime budget 집계
4. pause/resume 지원
5. loop run archive 지원

성공 기준:

- 같은 테스트 실패가 반복되면 무한 재실행하지 않고 pause한다.
- budget 초과 시 provider 호출 전에 멈춘다.

### Phase 3: Review/Judge gate

작업:

1. provider-backed review gate 추가
2. central judge prompt 추가
3. review result를 stop policy에 연결
4. post-review action item과 loop next action 연결

성공 기준:

- 테스트가 통과해도 reviewer가 high severity 문제를 내면 complete하지 않는다.
- reviewer가 같은 문제를 반복하면 사용자 결정을 요구한다.

### Phase 4: Local automation queue

작업:

1. `trinity loop enqueue`
2. `trinity loop worker --once`
3. queue claim/lock 파일
4. stale claimed run recovery

성공 기준:

- 여러 loop request가 순서대로 처리된다.
- worker 중단 후 stale claim을 감지하고 재시도/취소할 수 있다.

### Phase 5: GitHub connector

작업:

1. GitHub issue/PR/CI event adapter
2. PR comment/status writer
3. connector credential/readiness check
4. connector gate

성공 기준:

- CI failure를 loop input으로 받아 수정 PR 또는 comment를 남길 수 있다.
- connector 실패가 core loop state를 깨지 않는다.

### Phase 6: Textual Loop Dashboard

작업:

1. Loop list/status panel
2. current run/iteration timeline
3. gate result viewer
4. pause/resume/stop actions
5. ledger preview

성공 기준:

- 사용자가 Nexus에서 현재 workflow뿐 아니라 상위 loop 상태를 볼 수 있다.
- loop가 왜 멈췄는지 UI에서 즉시 확인할 수 있다.

## 테스트 전략

1. Unit tests
   - LoopSpec parser
   - LoopRun persistence
   - stop policy
   - gate result serialization
   - failure signature

2. Integration tests
   - fake WorkflowEngine으로 one-iteration loop 검증
   - fake command gate pass/fail 검증
   - pause/resume 상태 복구 검증

3. Contract tests
   - `.trinity/loops` 파일 layout
   - workflow id 연결
   - event JSONL schema

4. Manual smoke
   - WSL repo에서 `trinity loop run local-quality-loop --once`
   - 실패 테스트가 있는 branch에서 loop가 pause/iterate하는지 확인
   - target workspace guard가 기존 execution과 동일하게 작동하는지 확인

## 하지 말아야 할 것

- 처음부터 always-on daemon을 만들지 않는다.
- provider 한 곳의 native automation에 종속시키지 않는다.
- agent에게 "완료될 때까지 알아서 반복"만 시키지 않는다.
- loop state를 workflow session 안에 억지로 모두 넣지 않는다.
- GitHub connector를 core engine보다 먼저 만들지 않는다.
- 테스트/gate 증거 없이 agent의 "완료했습니다"를 완료 판정으로 쓰지 않는다.

## 최종 판단

가장 적절한 방법은 `LoopEngine`을 `WorkflowEngine` 위에 얇게 추가하는 것이다.

이 방식은 참조 글의 여섯 요소를 Trinity의 현재 구조에 자연스럽게 매핑한다. Worktree,
skill/resource, sub-agent, memory는 이미 상당 부분 있고, 빠진 것은 automation trigger와
loop-level state/gate다. 따라서 지금 필요한 첫 작업은 자동화 자체가 아니라 루프를 정의하고,
한 번 실행하고, 검증하고, 왜 멈췄는지 디스크에 남기는 최소 엔진이다.

추천 첫 구현 범위:

1. `LoopSpec`, `LoopRun`, `LoopGateResult` 모델
2. `.trinity/loops` persistence
3. manual CLI `trinity loop run/status/stop`
4. command gate와 workflow-state gate
5. loop ledger/events

이 범위가 안정화되면 그 다음에 provider review gate, queue, GitHub connector, Textual dashboard를
순서대로 붙이는 것이 안전하다.

## Phase 1 구현 메모

`feature/loop-engineering-mvp`에서 1차 구현을 반영했다.

추가된 범위:

- `src/trinity/loop/models.py`
  - `LoopSpec`, `LoopRun`, `LoopGateSpec`, `LoopGateResult`, `LoopStopPolicy`
- `src/trinity/loop/persistence.py`
  - `.trinity/loops/specs/*.toml` spec 로딩
  - `.trinity/loops/runs/<run-id>/loop.json`, `events.jsonl`, `ledger.md` 저장
  - iteration별 `gate-results.json` 저장
- `src/trinity/loop/gates.py`
  - `command` gate
  - `workflow-state` gate
- `src/trinity/loop/engine.py`
  - manual loop run
  - once/until-stop 반복
  - max iteration, runtime/token budget stop
  - gate 실패 시 pause/iterate policy
  - `DefaultWorkflowRunner`로 기존 `WorkflowEngine`/`TrinityOrchestrator` 호출
  - `NoopWorkflowRunner`로 provider 호출 없는 gate-only 진단
- `trinity loop run/status/stop`
  - `trinity loop run <spec-id-or-path>`
  - `trinity loop run <spec> --skip-workflow`
  - `trinity loop run <spec> --until-stop`
  - `trinity loop status [latest|run-id]`
  - `trinity loop stop [latest|run-id] --reason <text>`

검증:

- `PYTHONPATH=src ~/workspace/Trinity/.venv/bin/pytest tests/test_loop_engine.py tests/test_cli_loop.py -q`
  - `11 passed`
- `PYTHONPATH=src ~/workspace/Trinity/.venv/bin/pytest tests/test_cli.py tests/test_cli_v2.py tests/test_workflow_persistence.py tests/test_config.py tests/test_loop_engine.py tests/test_cli_loop.py -q`
  - `102 passed`
- `PYTHONPATH=src ~/workspace/Trinity/.venv/bin/pytest -q`
  - `1403 passed, 1 warning`
