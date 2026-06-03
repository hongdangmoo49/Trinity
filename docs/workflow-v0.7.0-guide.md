# Trinity v0.7.0 Workflow Guide

작성일: 2026-06-03

## 1. 목적

v0.7.0 workflow mode는 단발성 agent 토론을 상태 기반 작업 흐름으로 확장한다.
사용자 목표는 `WorkflowSession`으로 저장되고, Trinity는 provider readiness, 구조화된 설계,
사용자 의사결정, work package 실행, subtask report, review package 생성을 같은 lifecycle에서 추적한다.

구조화된 source of truth는 다음 파일이다.

```text
.trinity/workflow/session.json
.trinity/workflow/events.jsonl
```

`shared.md`는 사람이 읽는 요약 문서다. 손상되거나 수동 편집되어도 workflow state는
`session.json`과 `events.jsonl`에서 복구할 수 있어야 한다.

## 2. 빠른 시작

대화형 TUI를 실행한다.

```bash
cd /path/to/project
trinity
```

새 목표를 입력하면 Trinity는 다음 순서로 진행한다.

1. active agent와 workflow session을 만든다.
2. provider readiness를 확인한다.
3. round 기반 deliberation을 실행한다.
4. structured consensus가 나오면 blueprint를 저장한다.
5. blueprint를 active agent 수만큼 work package로 분해한다.
6. execution intent이면 work package를 owner agent에게 dispatch한다.
7. execution result, subtask report, review package를 workflow state와 shared ledger에 기록한다.

## 3. 주요 TUI 명령

| 명령 | 설명 |
|------|------|
| `/status` | agent provider, readiness, context 상태를 표시한다. |
| `/workflow` | workflow id, state, round, active agents, pending questions, package count를 표시한다. |
| `/questions` | 사용자의 결정이 필요한 open question을 표시한다. |
| `/decisions` | 사용자 또는 agent가 남긴 decision ledger를 표시한다. |
| `/packages` | blueprint에서 생성된 work package와 실행 상태를 표시한다. |
| `/subtasks` | parent agent가 보고한 provider-internal subtask/tool 사용 결과를 표시한다. |

## 4. Workflow State

| 상태 | 의미 |
|------|------|
| `idle` | 아직 active workflow가 없다. |
| `preflight` | 새 목표를 받았고 provider/readiness 준비 단계다. |
| `deliberating` | agent round loop가 진행 중이다. |
| `needs_user_decision` | blocking open question 또는 blocked package에 대해 사용자 답변이 필요하다. |
| `blueprint_ready` | consensus blueprint가 만들어졌고 work package가 준비됐다. |
| `executing` | work package가 owner agent에게 dispatch되고 있다. |
| `reviewing` | 실행이 끝났고 peer/self review package가 만들어졌다. |
| `done` | workflow가 완료됐다. |
| `failed` | consensus 또는 execution이 실패했다. |

## 5. Provider Readiness

Interactive provider는 시작 화면, 인증 화면, 모델 로딩 배너를 실제 답변처럼 출력할 수 있다.
v0.7.0은 deliberation 시작 전에 provider readiness를 분류한다.

| 상태 | 의미 | 기본 처리 |
|------|------|-----------|
| `ready` | prompt 입력 가능한 상태다. | deliberation 포함 |
| `auth_required` | 로그인/OAuth/API key 입력이 필요하다. | strict mode에서 중단 |
| `model_loading` | 모델 초기화 또는 다운로드/선택이 진행 중이다. | strict mode에서 중단 |
| `workspace_trust_required` | workspace trust/confirm UI가 대기 중이다. | strict mode에서 중단 |
| `cli_banner_only` | CLI banner만 있고 prompt readiness가 불명확하다. | strict mode에서 중단 |
| `process_dead` | provider process/pane이 죽었다. | 중단 또는 재시작 필요 |
| `unknown_not_ready` | 알려진 ready 패턴이 확인되지 않았다. | 중단 |

설정은 `.trinity/trinity.config`의 `[deliberation]`에서 조정한다.

```toml
[deliberation]
provider_readiness_mode = "strict"      # strict | degraded
provider_readiness_timeout_seconds = 20.0
```

`strict`는 하나라도 준비되지 않으면 deliberation을 시작하지 않는다.
`degraded`는 준비된 agent가 하나 이상 있으면 준비된 agent만으로 진행한다.

## 6. Structured Deliberation

각 agent 응답은 structured contract를 포함해야 한다.

```text
VOTE: APPROVE | APPROVE_WITH_CHANGES | BLOCKED_BY_QUESTION | REJECT
BLUEPRINT ...
OPEN QUESTIONS ...
```

Trinity는 structured vote를 평가해 다음 중 하나를 선택한다.

- consensus blueprint 저장
- open question 생성 후 `needs_user_decision` 전환
- consensus 실패 처리

사용자 답변은 새 workflow를 만들지 않고 기존 pending question의 decision으로 저장된다.
`needs_user_decision` 상태에서 일반 텍스트는 더 이상 첫 질문의 답변으로 자동 소비되지 않는다.
질문 답변은 명시적인 `/answer` 명령으로 기록해야 한다.

```text
/questions
/questions --select
/questions --select --all
/answer q-claude-002 LI.FI
/answer 2 TypeScript
/answer next "Telegram 먼저"
/answer 1
/answer --replace q-claude-002 Socket
/answer --replace dec-001 Socket
```

지원되는 답변 대상:

- `q-...` question id
- `/questions` 표시 순서의 1-based index
- `next` 또는 `first`
- `--replace` 사용 시 기존 `dec-...` decision id

`/answer 1`처럼 답변 내용 없이 숫자 하나만 입력하면, 첫 번째 pending question의
1번 option을 선택한다. `/questions --select`는 터미널이 대화형 TTY일 때 첫 번째
pending question의 options를 방향키로 선택하는 prompt_toolkit UI를 연다.
`/questions --select --all`은 pending question을 순서대로 처리하는 decision wizard다.
options가 있는 질문은 방향키로 고르고, options가 없는 질문은 같은 흐름에서 자유 텍스트를 입력한다.
명령형으로 처리하려면 `/answer next <answer>`를 사용한다.

Open question parser는 영어 contract와 한국어 agent 출력 변형을 모두 허용한다.

```text
OPEN QUESTIONS:
# 1
질문: 브릿지 API 소스?
옵션: LI.FI, Socket, 자체 구축
추천: LI.FI
이유: 현재 API 커버리지와 서버비 부담이 가장 낮음.

- Question: MVP scope?
  Options:
  1. L2 only
  2. L2 plus Ethereum mainnet
  Recommended: L2 plus Ethereum mainnet
  Rationale: Most practical bridge paths use Ethereum as a fallback.
```

## 7. Work Packages와 Execution

Blueprint consensus가 만들어지면 `BlueprintDecomposer`가 active agent마다 top-level work package를 만든다.

각 package는 다음 정보를 가진다.

- id
- owner agent
- objective
- scope/out-of-scope
- dependencies
- expected files
- acceptance criteria
- status

Execution intent가 있는 workflow에서는 `ExecutionProtocol`이 package owner에게 실제 작업 prompt를 보낸다.
응답은 다음 형식으로 보고해야 한다.

```text
## Completed
## Files Changed
## Decisions Made
## Blockers
## Follow-up
## Subtasks
```

결과는 `ExecutionResult`로 저장되고 `shared.md`의 `## Task Results`에 기록된다.

## 8. Subtask Reporting

Trinity는 Claude/Codex/Gemini 내부 subagent나 tool invocation을 직접 통제하지 않는다.
대신 parent agent에게 delegation report contract를 강제한다.

```text
## Subtasks
### ST-001
- delegated_to: <subagent/tool>
- objective: <input objective>
- result_summary: <output summary>
- status: done | blocked | failed
- decisions_made: <items or none>
- files_changed: <items or none>
- unresolved_issues: <items or none>
```

파싱된 결과는 `SubtaskResult`로 저장되고 `/subtasks` 및 `shared.md ## Subtasks`에 표시된다.

## 9. Lifecycle Guard와 Rotation

`LifecycleGuard`는 workflow traffic 전후에 다음 hook을 평가한다.

- `before_agent_call`
- `after_agent_call`
- `before_round`
- `after_round`
- `before_work_package`
- `after_work_package`

MVP 기준으로 다음 상태를 감시한다.

- process alive
- provider readiness
- current context ratio
- projected prompt ratio

context ratio 또는 projected ratio가 threshold를 넘으면 `SessionRotator`를 통해 다음 prompt 전에 session rotation을 권고하고 실행한다.

## 10. Peer Review

Execution이 모두 `done`이면 workflow는 `reviewing` 상태가 된다.
`PeerReviewPlanner`는 각 work package마다 최소 1개의 `ReviewPackage`를 만든다.

- active agent가 2개 이상이면 owner가 아닌 agent가 reviewer가 된다.
- active agent가 1개뿐이면 self-review package를 만든다.

현재 단계는 review package 계획과 persistence까지 제공한다. 실제 review prompt 실행은 후속 workflow loop에서 확장한다.
구체적인 후속 구현 후보는 [`docs/plans/2026-06-04-v0.7.0-follow-up-implementation-candidates.md`](plans/2026-06-04-v0.7.0-follow-up-implementation-candidates.md)에 정리한다.

## 11. Shared Ledger

`SharedLedgerRenderer`는 `WorkflowSession`과 provider readiness를 사람이 읽는 shared ledger로 렌더링한다.
기본 섹션은 다음 순서를 유지한다.

```markdown
# Shared Context

## Current Goal
## Workflow State
## Provider Readiness
## Decisions
## Open Questions
## Blueprint
## Work Packages
## Task Results
## Subtasks
## Round Opinions
## Response Diagnostics
## Session History
```

`WorkflowEngine.sync_shared_ledger(shared, provider_readiness=...)`는 `session.json` 상태를 기준으로 shared.md를 다시 쓴다.
이때 round opinions, response diagnostics, session history 같은 freeform log section은 기존 shared.md에서 보존한다.

## 12. 운영 팁

- Provider auth/readiness 문제가 있으면 `/status`를 먼저 본다.
- Open question이 있으면 새 목표를 입력하지 말고 해당 질문에 답한다.
- `shared.md`를 직접 수정해야 한다면, 구조화 상태는 `session.json`이 우선이라는 점을 전제로 한다.
- 실제 tmux smoke는 WSL native repo에서 실행한다.

```bash
cd /home/zaemi/workspace/Trinity
uv run trinity
```
