# Trinity 현재 워크플로우 동작 분석

작성일: 2026-06-12

브랜치: `feature/current-workflow-operation-analysis`

기준 소스: `main` 최신, Trinity `0.12.9`

## 목적

`2026-06-11-workflow-vision-gap-analysis.md`는 사용자가 기대한 최종 워크플로우와
당시 구현의 차이를 분석했다. 이후 다음 축의 보강이 반영되었다.

- 질문 답변 후 대상 agent/model 유지
- WP당 모든 non-owner agent 리뷰
- 중앙 에이전트 provider session 지속성
- final review 수정사항 자동 보강 WP 생성
- 중앙 에이전트 blueprint 본문과 다음 행동 버튼
- Nexus 보강 액션 버튼의 대상 agent/model 컨텍스트 유지
- review UI 성능/표시 개선과 report audit trail 보강

이 문서는 현재 `main` 기준으로 Trinity workflow가 실제로 어떤 순서와 상태로
동작하는지 정리한다.

## 한 줄 요약

현재 Trinity는 "사용자 목표 입력 -> 선택된 agent/model로 provider 협의 -> 중앙
에이전트 synthesis -> 질문 또는 blueprint -> 사용자 승인 실행 -> WP 실행 -> 모든
non-owner agent 리뷰 -> repair loop -> final review -> 필요한 보강 WP 자동 생성"까지
이어지는 persisted workflow로 동작한다.

실제 파일 변경은 여전히 사용자가 `Execute` 또는 `/execute`를 선택하고 target
workspace preflight를 통과해야 시작된다. Final review가 보강 작업을 만들더라도 즉시
실행하지 않고, 새 `WP-S###`를 대기 상태로 만든 뒤 다시 사용자 승인 지점으로 돌아간다.

## 전체 단계

```text
Start/Nexus prompt
  -> selected target agents + model overrides
  -> WorkflowEngine.start() 또는 continue/answer
  -> TrinityOrchestrator.ask()
  -> ProviderReadinessGate
  -> DeliberationProtocol round(s)
  -> worker provider session/runtime model 기록
  -> central model-backed synthesis
  -> central provider session/runtime model 기록
  -> NEEDS_USER_DECISION 또는 BLUEPRINT_READY
  -> 중앙 blueprint 본문 + 다음 작업 버튼
  -> Execute preflight
  -> ExecutionProtocol dependency-safe batch 실행
  -> REVIEWING
  -> 모든 non-owner WP review
  -> review repair loop 또는 final review
  -> POST_REVIEW_READY 또는 final-review auto replan
  -> supplemental WP-S### 대기
```

## 1. Start/Nexus 입력과 대상 선택

Start 화면과 Nexus 화면에는 agent 대상 선택 UI와 model override UI가 있다. 사용자가
Claude, Codex, Antigravity 중 일부만 선택하거나 `/model`, `/ask --model`로 모델을
바꾸면 이 정보가 workflow action에 함께 들어간다.

현재 저장/전달되는 값은 다음과 같다.

- `target_agents`
- `agent_model_overrides`
- `agent_selection_mode`
- `WorkflowSession.last_target_agents`
- `WorkflowSession.agent_model_overrides`

처음 workflow를 시작하면 `WorkflowEngine.start()`가 선택 agent를
`last_target_agents`로 저장하고, 선택 agent에 허용되는 모델 override만 정규화해
세션에 저장한다. 이후 Textual controller는 이 action 값을 `TrinityOrchestrator`에
넘겨 실제 active provider set을 필터링한다.

## 2. 질문 답변 후 대상 agent/model 유지

기존 gap 문서의 주요 문제는 질문에 답한 뒤 대상 agent/model이 전체 active agent로
확장될 수 있다는 점이었다. 현재는 `WorkflowEngine.answer_question()`이 세션에 저장된
`last_target_agents`와 `agent_model_overrides`를 다시 `WorkflowInputAction`에 담아
반환한다.

따라서 사용자가 처음에 Codex만 선택한 상태에서 중앙 질문에 답하면, 다음 deliberation도
Codex 대상 설정과 Codex model override를 유지한다. 열린 질문이 더 남아 있으면 provider
호출을 다시 시작하지 않고 `NEEDS_USER_DECISION` 상태를 유지한다.

## 3. Provider one-shot 호출과 세션 지속성

각 worker agent 호출은 기본적으로 one-shot CLI 호출이다.

- Claude: `claude -p --output-format json`
- Codex: `codex exec --json`
- Antigravity: `agy --print`

하지만 one-shot이라고 해서 Trinity 세션이 끊기는 것은 아니다. Provider가 native
session id를 반환하면 Trinity가 이를 `WorkflowSession.provider_sessions`에 저장하고,
다음 read-only deliberation/review 호출 때 agent wrapper에 다시 주입한다.

현재 provider별 연결 방식은 다음과 같다.

| Provider | 저장되는 native id | 다음 호출 연결 방식 |
| --- | --- | --- |
| Claude | `session_id` | `--resume <session_id>` |
| Codex | `thread_id` | `codex exec resume <thread_id>` |
| Antigravity | `conversation_id` | `--conversation <conversation_id>` |

런타임 모델 정보도 `WorkflowSession.runtime_models`에 저장된다. 이를 통해 UI와
report는 "사용자가 설정한 모델"과 "실제 관찰된 모델/컨텍스트 정보"를 구분해 보여줄 수
있다.

## 4. 중앙 에이전트 synthesis와 중앙 provider session

중앙 에이전트는 별도의 local LLM이 아니라, 설정된 provider agent 중 하나를 사용해
model-backed synthesis를 시도한다. 기본 우선순위는 Codex, Claude, Antigravity 순이다.
실패하면 heuristic synthesis로 fallback한다.

현재 중앙 synthesis는 worker agent session과 충돌하지 않도록 별도 logical owner를 쓴다.

```text
central:codex
central:claude
central:antigravity
```

예를 들어 Codex가 중앙 synthesis provider이면 `agent_name`은 사용자-facing으로
`codex`이지만 provider session owner는 `central:codex`가 된다. 이 값은 provider
session metadata와 runtime model metadata에 반영되고, workflow resume 이후 중앙
synthesis도 이전 중앙 provider-native 대화를 이어갈 수 있다.

중앙 synthesis 결과는 다음 중 하나로 workflow에 반영된다.

- open question 생성 -> `NEEDS_USER_DECISION`
- structured blueprint 생성 -> `BLUEPRINT_READY`
- consensus fallback blueprint 생성 -> `BLUEPRINT_READY`
- 합의 실패 -> `FAILED`

중앙 blueprint가 생성되면 `central_conversation_recorded` 이벤트도 남는다. 이 기록은
Nexus 중앙 패널, report, audit trail에서 중앙 에이전트가 어떤 설계를 했는지 복원하는
근거가 된다.

## 5. 중앙 blueprint 화면과 다음 행동 버튼

`BLUEPRINT_READY` 상태가 되고 WP가 있으면 Nexus 중앙 패널은 단순 WP 목록만 보여주지
않는다. 현재는 중앙 blueprint 본문을 Markdown으로 재구성해 보여준다.

포함되는 주요 정보:

- 제목과 요약
- Architecture
- Data Flow
- Acceptance Criteria
- Work package graph
- 질문/결정/실행 로그 요약

그리고 다음 작업 버튼이 표시된다.

| 버튼 | 동작 |
| --- | --- |
| 실행 | execute preflight 또는 execution 시작 |
| 기능 보강 | 핵심 기능, 게임 루프, UX, 빠진 결정을 더 구체화하는 follow-up 전송 |
| 리스크 보강 | 실행 리스크, 안티패턴, 성능 우려, 검증 기준을 더 구체화하는 follow-up 전송 |
| WP 재분배 | WP 범위, 담당 agent, 의존성, 병렬 가능성을 다시 검토하는 follow-up 전송 |

보강 버튼은 일반 composer follow-up과 같은 `_submit_follow_up()` 경로를 탄다. 따라서
현재 선택된 target agent와 model override를 그대로 유지한다. 이 부분은 `기능 보강`,
`리스크 보강`, `WP 재분배` 모두 같은 `refine-*` 경로라 동일하게 처리된다.

## 6. Execute preflight와 target workspace guard

Planning은 workspace 없이 가능하다. 실제 파일 변경은 사용자가 `Execute`를 누르거나
`/execute`를 입력한 뒤 target workspace를 선택해야 시작된다.

Preflight는 다음을 확인한다.

- 경로 존재 여부
- 디렉터리 여부
- 쓰기 가능 여부
- Git repo 여부와 branch
- control repo 내부인지 여부
- 새 폴더 생성 가능 여부
- provider readiness snapshot

Control repo에 직접 쓰는 것은 기본 차단된다. 사용자가 명시적으로 확인해야 한다.
새 target folder 생성은 preflight picker에서 선택/생성된 경로를 workflow target으로
저장한 뒤 실행 단계에서 사용된다.

## 7. Work package 실행

`WorkflowEngine.begin_execution()`은 실행 대상 WP를 고르고 execution run을 만든다.
`ExecutionProtocol`은 dependency-ready WP만 batch로 묶고, `ParallelExecutionPolicy`가
다음 정보를 보며 병렬 가능성을 판단한다.

- WP dependency
- expected file ownership
- risk
- parallelizable flag
- parallel_group

실행 결과는 `ExecutionResult`로 저장되고, WP status는 `done`, `failed`, `blocked`,
`waiting_on_decision` 등으로 반영된다.

중요한 제약:

- Deliberation/review는 read-only provider session resume을 적극 사용한다.
- Execution은 workspace-write lane이므로 현재 controller가 worker provider session을
  그대로 넘기지 않는다.
- 즉 실행은 "이전 대화 native session"보다는 workflow decision, blueprint, shared
  context, target workspace를 통해 이어진다.

이 정책은 안전하지만, "쓰기 실행도 provider-native session을 반드시 이어야 한다"는
요구와는 다르다. 향후에는 read-only lane과 workspace-write lane의 provider session
정책을 명시적으로 분리해 UI에 표시하는 것이 좋다.

## 8. WP 완료 후 모든 non-owner agent 리뷰

기존 gap 문서에서는 WP당 리뷰어가 한 명만 선택되는 문제가 있었다. 현재
`PeerReviewPlanner.plan_reviews()`는 각 WP에 대해 작업 owner/executor가 아닌 모든 active
agent에게 review package를 만든다.

예를 들어 active agent가 Claude, Codex, Antigravity이고 Codex가 `WP-001`을 수행했다면:

- Claude가 `WP-001` 리뷰
- Antigravity가 `WP-001` 리뷰

단일 active agent 세션에서는 self-review를 허용한다.

`review_packages_for_request("wp")`는 review package 단위로 pending review를 계산한다.
따라서 한 리뷰어가 approve했더라도 다른 리뷰어가 아직 리뷰하지 않았다면 해당 WP의
남은 review package가 계속 선택된다.

## 9. Review repair loop

WP review 결과 중 하나라도 `changes_requested`가 나오면 workflow는 repair loop로
들어간다. `prepare_review_repairs()`는 같은 WP에 대한 여러 reviewer의 required changes를
병합하고, 원래 작업한 executor가 다시 수정할 수 있도록 WP를 `pending`으로 되돌린다.

보호 장치도 있다.

- `repair_attempt_count`가 설정된 최대 횟수를 넘으면 blocked 처리
- 동일 required changes가 반복되면 duplicate repair로 blocked 처리
- blocked review repair는 Nexus에서 사용자가 재시도, 완료 처리, 리뷰 보기, 중단 중 선택

이 repair loop는 사용자가 기대한 "리뷰를 받으면 해당 WP를 작업했던 에이전트가 이어서
한다"는 흐름과 대체로 일치한다.

## 10. Final review

모든 WP review가 승인되면 final project review가 실행된다. Final reviewer fallback
우선순위는 다음과 같다.

```text
codex -> claude -> antigravity
```

Final review는 개별 WP가 아니라 프로젝트 전체를 본다.

주요 관점:

- 전체 호환성
- 프로젝트 구조와 실행 방법
- 실행에 심각한 오류
- 안티패턴
- 성능 우려
- 검증/테스트 누락
- 추가로 필요한 기능이나 보강점

Final review 결과는 `ReviewResult(scope="final")`로 저장되고 post-review action item으로
정규화된다.

## 11. Final review 자동 보강 WP 생성

현재 final review가 `CHANGES_REQUESTED`이고 새 action item 중 `bugfix` 또는
`validation` 성격의 필수 실행 항목이 있으면, target workspace가 존재하는 경우 자동으로
supplemental WP를 만든다.

동작 순서:

1. final review findings를 `PostReviewActionItem`으로 정규화
2. final review에서 나온 required execution item 중 `bugfix`, `validation` 선별
3. target workspace가 있으면 자동 accept
4. `WP-S###` supplemental work package 생성
5. execution run source를 `final_review_auto_replan`으로 표시
6. workflow를 다시 `BLUEPRINT_READY`로 전환

중요한 점은 여기서 실행을 자동 시작하지 않는다는 것이다. Trinity는 중앙 workflow가
보강 WP를 준비해두고, 사용자가 다시 `Execute`를 선택하기를 기다린다.

Target workspace가 없으면 자동 보강 WP 생성은 skip되고 `POST_REVIEW_READY`로 남는다.
이 경우 사용자가 target을 지정하거나 `/improve` 계열 명령으로 수동 보강 흐름을 사용할
수 있다.

## 12. Post-review follow-up과 추가 요청

Final review 이후 사용자가 Nexus에서 추가 요청을 입력하면 상태에 따라 다르게 처리된다.

- `POST_REVIEW_READY`: `handle_post_review_input()`이 action item 선택 또는 자유 보강 요청을
  supplemental WP로 연결한다.
- `BLUEPRINT_READY`, `DONE`, `FAILED`, `REVIEWING`: `continue_from_blueprint()`가 기존
  blueprint 기반 추가 협의 또는 새 실행 요청으로 분기한다.
- 명시적으로 execute 의도가 감지되면 현재 blueprint를 executable WP로 재생성한다.

따라서 최종 보고 이후에도 같은 workflow session 안에서 보강 요청을 이어갈 수 있다.

## 13. Resume과 execute retry

Workflow 상태는 `.trinity/workflow/session.json`, `events.jsonl`, history archive에
저장된다. TUI는 기본적으로 새 workflow를 시작하지만, `/resume`으로 이전 workflow를
선택해 active session으로 복원할 수 있다.

복원 후:

- workflow snapshot이 Nexus에 표시된다.
- provider session/runtime model metadata가 orchestrator에 다시 전달된다.
- 중앙 synthesis도 `central:<agent>` session key로 이어질 수 있다.
- context 표시와 report/audit 자료는 현재 session projection 기준으로 구성된다.

실행 중단/실패 복구는 `/execute-retry`가 담당한다.

지원 selector:

- `all`
- `failed`
- `blocked`
- `interrupted`
- `custom`
- 직접 WP-ID 목록

Textual에서는 modal로 WP 목록, 상태, topic, retry 가능 여부를 보여주고 custom 선택 시
checkbox로 직접 선택한다.

## 14. Context와 memory 관리

Trinity는 원본 로그를 무한히 provider prompt에 그대로 넣지 않는다. 현재 구조는 다음처럼
분리되어 있다.

- workflow 원본 상태: `session.json`, `events.jsonl`
- provider raw/clean response artifact
- shared context projection: `shared.md`
- memory index: `.trinity/memory/index.sqlite`
- report/audit reconstruction source: central conversation, events, review/execution records

`shared.md`는 bounded projection을 유지하고, `/memory stats`, `/memory compact`,
`/artifact <memory-id>` 명령으로 memory 상태를 확인하거나 compact projection을 다시 만들 수
있다. 오래된 상세 내용은 memory/artifact로 보존하고, provider prompt에는 필요한 요약과
최근 정보만 넣는 방향이다.

## 기존 gap 항목의 현재 상태

| 기존 gap | 현재 상태 | 비고 |
| --- | --- | --- |
| 질문 답변 후 대상 agent/model 유지 안 됨 | 해결 | `answer_question()`이 `last_target_agents`, `agent_model_overrides`를 action에 포함 |
| 중앙 에이전트 provider session 미저장 | 해결 | `central:<agent>` logical owner로 provider session/runtime model 저장 |
| WP당 한 명만 리뷰 | 해결 | 모든 non-owner active agent review package 생성 |
| Final review 수정사항 자동 재계획 없음 | 해결 | required bugfix/validation item을 `WP-S###`로 자동 queue |
| 중앙 blueprint 본문이 화면에 충분히 안 보임 | 해결 | central conversation/blueprint Markdown과 다음 행동 버튼 추가 |
| Nexus 보강 버튼이 대상/model 컨텍스트를 잃음 | 해결 | `refine-*` 버튼이 `_submit_follow_up()` 경로를 사용 |
| `next_round_prompt`가 다음 라운드 주요 지시문으로 승격되지 않음 | 남은 제약 | shared context에는 남지만 `_build_round_prompt()`는 generic round2 prefix를 계속 사용 |
| workspace-write execution도 provider-native session을 이어야 하는가 | 정책 미정 | 현재 execution lane은 안전상 별도 호출 성격이 강함 |

## 현재 남은 제약

### 1. `next_round_prompt`는 직접 지시문이 아니라 context에 가깝다

중앙 synthesis가 `next_round_prompt`를 만들고 shared context에 저장할 수는 있다. 하지만
round 2+ prompt 생성은 여전히 "previous round opinions + generic round2 prefix" 구조다.
즉 중앙 에이전트가 다음 라운드의 핵심 비교 지시문을 만들더라도, 그것이 다음 prompt의
최상위 명령으로 승격되는 구조는 아직 아니다.

### 2. Execution lane provider session 정책은 명확히 문서화가 필요하다

Deliberation과 review는 read-only session continuity가 강하다. 반면 execution은
workspace-write이고 controller가 provider session을 그대로 넘기지 않는다. 안전한 정책일 수
있지만, 사용자는 "같은 에이전트 세션이 계속 이어진다"고 이해할 수 있다. UI나 문서에서
"설계/리뷰 대화 session"과 "쓰기 실행 turn"의 차이를 분명히 보여줄 필요가 있다.

### 3. URL 입력은 자동 웹 수집 워크플로우가 아니다

사용자가 URL을 prompt에 넣어도 현재 Trinity가 직접 URL을 fetch/crawl해 동일 본문을
각 provider에게 넘기지는 않는다. URL은 prompt text로 전달되고, 실제 웹 접근 여부는 각
provider CLI의 자체 기능/권한/도구 설정에 의존한다. 신뢰 가능한 URL 분석 workflow를
원하면 Trinity 레벨의 URL fetch -> artifact -> shared context projection 단계가 필요하다.

## 현재 기대 UX

1. 사용자는 Start 화면에서 목표를 쓰고 대상 agent/model을 고른다.
2. Nexus에서 provider 카드가 running/ready 상태로 바뀌며, 중앙 에이전트가 synthesis한다.
3. 질문이 있으면 중앙 영역에 질문과 선택지가 버튼으로 표시된다.
4. 질문 답변 후에도 처음 고른 대상 agent/model이 유지된다.
5. blueprint가 준비되면 중앙 설계 본문과 WP graph가 보인다.
6. 사용자는 실행, 기능 보강, 리스크 보강, WP 재분배 중 하나를 고른다.
7. 실행은 workspace preflight 후 시작된다.
8. WP가 끝나면 모든 non-owner agent 리뷰가 실행된다.
9. 리뷰 수정 요청이 있으면 원 작업자가 repair를 수행한다.
10. 모든 WP 리뷰가 통과하면 final review가 실행된다.
11. final review에서 필수 수정이 있으면 supplemental WP가 자동 생성된다.
12. 사용자는 새 WP를 확인하고 다시 Execute할 수 있다.
13. 중단/실패/종료 후에는 `/resume`과 `/execute-retry`로 이어간다.

## 결론

현재 Trinity workflow는 기존 gap analysis에서 지적된 핵심 네 가지 문제를 대부분
해결했다. 이제 동작 모델은 단순한 "세 provider에게 물어보고 요약"이 아니라, 중앙
에이전트가 session-aware synthesis를 수행하고, WP 실행과 다중 리뷰, repair, final review,
자동 보강 WP 생성까지 이어지는 닫힌 루프에 가깝다.

남은 중요한 개선은 다음 두 가지다.

1. 중앙 synthesis의 `next_round_prompt`를 다음 라운드 주요 지시문으로 승격할지 결정한다.
2. execution lane의 provider-native session 지속성 정책을 사용자에게 명확히 설명하거나,
   read-only/workspace-write session을 분리해 구현한다.

이 두 지점을 정리하면 "기획한 workflow"와 "실제 사용자가 보는 workflow" 사이의 설명
간극은 대부분 사라진다.

