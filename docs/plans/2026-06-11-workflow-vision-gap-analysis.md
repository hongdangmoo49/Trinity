# Trinity 워크플로우 기획-구현 비교 분석

작성일: 2026-06-11
분석 브랜치: `feature/workflow-vision-gap-analysis`
기준 소스: `main` 최신 커밋 `f826a88` + 버전 커밋 `54275a4`

## 목적

사용자가 원하는 Trinity 동작은 "세 에이전트가 라운드별로 의견을 내고, 중앙 에이전트가 이를 종합해 질문 또는 실행 가능한 work package를 만들며, 실행 후 상호 리뷰와 최종 리뷰를 거쳐 다시 보강 작업으로 이어지는" 닫힌 루프이다.

이 문서는 현재 코드가 그 흐름을 어디까지 지원하는지, 그리고 기획과 다르게 동작하는 지점을 구현 근거와 함께 비교한다.

## 기획 요구사항 분해

1. 최초 prompt 입력 시 선택된 대상 에이전트만 round 1을 수행한다.
2. round 1 호출은 one-shot이지만, 각 provider의 session ID를 Trinity workflow session에 저장한다.
3. 중앙 에이전트가 각 provider 결과를 요약/분석해 사용자 질문 또는 work package/blueprint를 만든다.
4. 사용자가 질문에 답하면 기존 요약과 사용자 응답을 더해 같은 대상 에이전트에게 round 2 prompt를 보낸다.
5. round 2 이후도 provider session ID를 사용해 직전 provider 대화와 이어져야 한다.
6. 합의가 안 되면 round 3 이상으로 이어지고, 합의되면 중앙 에이전트가 요구사항 전체를 만족하는 work package DAG를 만든다.
7. execute 시 지정 디렉터리에서 work package를 의존성/병렬 가능성에 따라 수행한다.
8. 각 work package 완료 후 해당 작업자가 아닌 다른 에이전트들이 리뷰한다. 예: Codex 작업물은 Claude와 Agy가 모두 리뷰한다.
9. 전체 work package가 끝나면 중앙/최종 리뷰어가 프로젝트 전체를 리뷰한다.
10. 최종 리뷰에서 수정사항이 있으면 사용자에게 중간 보고 후 추가 work package를 만들고 다시 할당한다.
11. 최종 리뷰에서 수정사항이 없으면 사용자에게 보고만 한다.
12. 사용자가 최종 보고 후 Nexus에서 추가 prompt를 입력하면 같은 세션에서 추가 작업을 이어갈 수 있다.

## 현재 구현 요약

현재 구현은 큰 흐름을 상당 부분 갖추고 있다. Start/Nexus UI는 agent 선택과 model override를 workflow controller로 전달한다. DeliberationProtocol은 선택된 에이전트들에게 병렬로 one-shot prompt를 보내고, provider session/model metadata를 workflow session에 저장한다. 중앙 synthesis는 model-backed synthesis를 우선 시도하고 실패하면 heuristic으로 폴백한다. 구조화된 synthesis 결과가 open question을 내면 사용자의 결정을 기다리고, blueprint가 나오면 WorkPackage로 분해된다. Execute는 target workspace 경계를 확인하고, dependency와 file ownership 기반 병렬 정책으로 work package를 수행한다. 실행 완료 후 work-package review와 final review도 있다.

하지만 사용자가 의도한 "모든 리뷰어가 리뷰하는 WP 리뷰", "질문 답변 후 같은 대상/모델로 이어지는 라운드", "최종 리뷰 수정사항을 중앙 에이전트가 다시 work package로 재계획하는 루프", "중앙 에이전트 자체의 세션 지속성"은 아직 부분 구현 또는 미구현이다.

## 단계별 비교

| 단계 | 기획 | 현재 구현 | 판정 |
| --- | --- | --- | --- |
| 최초 입력 대상 선택 | 선택된 1~3개 에이전트만 round 1 수행 | StartScreen/NexusScreen이 `target_agents`, `agent_model_overrides`를 전달하고, Orchestrator가 `active_agent_names`로 agent set을 필터링한다. 근거: `src/trinity/textual_app/screens/start.py:171-181`, `src/trinity/textual_app/app.py:1051-1068`, `src/trinity/textual_app/workflow_controller.py:109-136`, `src/trinity/orchestrator.py:162-179` | 일치 |
| one-shot provider 호출 | 각 에이전트가 one-shot으로 응답 | DeliberationProtocol이 `_collect_opinions()`에서 각 agent의 `send_and_wait()`를 병렬 task로 실행한다. 근거: `src/trinity/deliberation/protocol.py:397-420` | 일치 |
| provider session 저장 | provider별 session ID를 Trinity workflow에 저장 | provider metadata를 `provider_sessions`로 수집하고 WorkflowSession에 저장한다. 테스트도 존재한다. 근거: `src/trinity/deliberation/protocol.py:527-545`, `src/trinity/workflow/engine.py:658-683`, `tests/test_workflow_engine.py:200-242` | 일치 |
| provider session 이어가기 | 다음 provider 호출이 직전 세션과 이어짐 | Orchestrator가 read-only provider session을 agent wrapper에 주입하고, Claude는 `--resume`, Codex는 `codex exec resume`, Agy는 `--conversation`을 사용한다. 근거: `src/trinity/orchestrator.py:604-631`, `src/trinity/providers/invoker.py:263-270`, `src/trinity/providers/invoker.py:407-424`, `src/trinity/providers/invoker.py:698-708` | 부분 일치 |
| 중앙 에이전트 종합 | 중앙 에이전트가 요약/분석/질문/work package 생성 | model-backed synthesis가 provider 결과를 strict JSON으로 정규화하고, 질문/blueprint/work_packages schema를 요구한다. heuristic fallback도 있다. 근거: `src/trinity/orchestrator.py:390-456`, `src/trinity/deliberation/synthesis.py:145-225`, `src/trinity/deliberation/synthesis.py:242-340` | 부분 일치 |
| 질문 답변 후 round 2 | 사용자 답변과 기존 요약을 더해 같은 대상 에이전트에게 다시 prompt | `answer_question()`은 decision continuation prompt를 만들고 deliberation을 다시 시작한다. 그러나 반환 action에 `target_agents`와 `agent_model_overrides`가 들어가지 않는다. 따라서 최초 선택 대상이 아니라 config의 모든 active agent로 확장될 수 있다. 근거: `src/trinity/workflow/engine.py:296-376`, `src/trinity/textual_app/workflow_controller.py:521-558` | 불일치 가능 |
| next round prompt 사용 | 중앙 에이전트가 round 2/3의 방향을 정함 | `next_round_prompt`는 shared.md의 `Round N Synthesis`에 저장되고 다음 라운드 context에 포함된다. 하지만 `_build_round_prompt()`는 이를 직접 다음 prompt 본문으로 쓰지 않고 generic `round2_plus_prefix`를 붙인다. 근거: `src/trinity/context/shared.py:356-388`, `src/trinity/context/shared.py:411-490`, `src/trinity/deliberation/protocol.py:929-978` | 부분 일치 |
| 합의 시 work package DAG | 요구사항 전체와 선행/병렬 관계를 고려한 WP 생성 | structured blueprint의 `work_packages`를 검증/정규화하고, dependency/expected_files/parallelizable/risk/parallel_group을 보존한다. fallback decomposer도 있다. 근거: `src/trinity/workflow/engine.py:658-690`, `src/trinity/workflow/decomposer.py:82-143`, `src/trinity/workflow/decomposer.py:145-249` | 부분 일치 |
| execute target workspace | 사용자가 지정한 디렉터리에서 실행 | target workspace가 없으면 실행 요구가 반환되고, 실행 프로토콜은 control repo write를 가드한다. 근거: `src/trinity/workflow/engine.py:490-560`, `src/trinity/workflow/execution.py:173-198` | 일치 |
| 병렬 execute | 의존성이 없는 work package는 병렬 수행 | ExecutionProtocol은 dependency-ready package를 batch로 묶고 `asyncio.gather()`로 실행한다. ParallelExecutionPolicy가 file ownership/risk/parallelizable/parallel_group을 본다. 근거: `src/trinity/workflow/execution.py:122-171`, `src/trinity/workflow/execution.py:205-240`, `src/trinity/providers/policy.py:116-246` | 일치 |
| WP 완료 후 다른 에이전트 리뷰 | Codex 작업은 Claude와 Agy가 모두 리뷰 | 현재 PeerReviewPlanner는 work package당 리뷰어 1명만 선택한다. 실패 시 다른 리뷰어로 fallback할 뿐, 모든 non-owner 리뷰어가 동시에/순차적으로 리뷰하지 않는다. 근거: `src/trinity/workflow/review.py:177-237`, `src/trinity/workflow/review_execution.py:50-121`, `tests/test_peer_review.py:32-52` | 불일치 |
| WP 리뷰 수정 반영 | 리뷰에서 변경 요청 시 원 작업자가 이어서 보강 | `prepare_review_repairs()`가 changes_requested WP를 다시 pending으로 돌리고, controller가 자동으로 execution을 재시작한다. 반복/중복 변경은 blocked로 가드한다. 근거: `src/trinity/workflow/engine.py:1248-1345`, `src/trinity/textual_app/workflow_controller.py:470-490`, `tests/test_textual_workflow_controller.py:727-780` | 대체로 일치 |
| 전체 최종 리뷰 | 모든 WP 후 프로젝트 전체 리뷰 | work package 리뷰가 모두 통과하면 final review를 실행하고, fallback 순서는 codex -> claude -> antigravity이다. 근거: `src/trinity/workflow/review.py:25-29`, `src/trinity/workflow/review_execution.py:123-159` | 일치 |
| 최종 리뷰 수정사항 처리 | 중앙 에이전트가 중간 보고 후 새 WP를 만들고 재할당 | final review가 changes_requested여도 즉시 중앙 에이전트가 재계획하지 않는다. `post_review_items`를 만들고 `POST_REVIEW_READY`에서 사용자가 `/improve high/all/...` 같은 선택을 해야 supplemental WP가 추가된다. 근거: `src/trinity/workflow/engine.py:1635-1680`, `src/trinity/workflow/engine.py:1712-1805`, `tests/test_workflow_engine.py:1125-1179` | 부분 일치 |
| 최종 리뷰 통과 보고 | 수정사항 없으면 사용자에게 보고 | final review approved도 `POST_REVIEW_READY`로 이동하고 post-review item이 없으면 사용자가 `/improve done` 등으로 닫을 수 있다. UI 보고는 snapshot/central view에 의존한다. 근거: `src/trinity/workflow/engine.py:1635-1680`, `tests/test_workflow_engine.py:1096-1123` | 부분 일치 |
| 최종 보고 후 Nexus 추가 prompt | Nexus에서 추가 작업을 이어감 | `POST_REVIEW_READY`에서 free text는 `handle_post_review_input()`으로 들어가 supplemental WP를 만들거나 기존 action item을 선택한다. blueprint 이후 일반 follow-up은 `continue_from_blueprint()`로 다시 deliberation 가능하다. 근거: `src/trinity/workflow/engine.py:209-227`, `src/trinity/workflow/engine.py:411-489`, `src/trinity/workflow/engine.py:1712-1805` | 부분 일치 |

## 주요 차이와 위험

### 1. 질문 답변 후 대상 에이전트/모델 선택이 유지되지 않는다

최초 시작과 일반 follow-up은 `target_agents`와 `agent_model_overrides`를 action에 담아 orchestrator로 넘긴다. 그러나 pending question에 답하는 `answer_question()` 경로는 `WorkflowInputAction`에 이 값을 넣지 않는다.

결과적으로 사용자가 처음에 Codex만 선택했더라도, 중앙 질문에 답한 뒤에는 `_start_deliberation()`이 빈 `target_agents`를 받아 config의 모든 active agent를 사용할 수 있다. 이건 "사용자가 1개만 설정했으면 1개 에이전트만 계속 수행"이라는 기획과 다르다.

권장 수정:

- `answer_question()`이 `session.last_target_agents`와 `session.agent_model_overrides`를 action에 포함하도록 수정한다.
- 관련 테스트를 추가한다. 예: targeted session에서 question answer 후 action target이 유지되는지 검증.

### 2. 중앙 에이전트 session ID가 provider agent처럼 저장되지 않는다

Claude/Codex/Agy provider session은 `provider_sessions`에 저장된다. 그러나 중앙 synthesis는 `ModelBackedSynthesisAgent`가 provider invoker를 직접 호출하고, 결과 metadata에는 provider/model/status/request_id만 저장한다. synthesis provider의 native session ID를 workflow session에 `central_agent` 같은 키로 저장하고 다음 synthesis에 resume하는 구조는 없다.

기획상 "세 에이전트 + 중앙 에이전트의 ID가 각각 Trinity session 하위에 있다"는 모델과 맞추려면 중앙 synthesis도 `ProviderSessionRef`로 저장해야 한다.

권장 수정:

- `ModelBackedSynthesisAgent`의 `PromptRequest`에 중앙 provider session ID를 받을 수 있게 한다.
- synthesis `ProviderTurnResult.metadata["provider_session"]`을 `DeliberationResult.metadata`에 포함한다.
- WorkflowSession에 `central_provider_session` 또는 provider_sessions key convention을 추가한다. 예: `synthesis:codex`.

### 3. `next_round_prompt`는 저장되지만 다음 라운드 prompt를 직접 대체하지 않는다

중앙 synthesis는 `next_round_prompt`를 만들 수 있고, shared.md에도 `Round N Synthesis > Next Round Prompt`로 저장된다. 다음 라운드 prompt는 shared.md context를 포함하므로 간접적으로 보이긴 한다. 하지만 `_build_round_prompt()`는 항상 "Previous round opinions + generic round2 prefix" 형태를 만든다.

기획상 중앙 에이전트가 "합의가 안 되었으니 다음 라운드에서 무엇을 비교/해결할지"를 명확히 지시해야 한다면, `next_round_prompt`를 다음 라운드의 주요 지시문으로 승격해야 한다.

권장 수정:

- DeliberationProtocol run loop에서 `last_next_round_prompt`를 보관한다.
- round 2+ prompt에 generic prefix 대신 중앙 synthesis의 `next_round_prompt`를 우선 사용한다.
- 없을 때만 기존 localized `round2_plus_prefix`로 fallback한다.

### 4. WP 리뷰가 "다른 모든 에이전트 리뷰"가 아니라 "한 명 리뷰 + fallback"이다

현재 `PeerReviewPlanner.plan_reviews()`는 WP당 리뷰 패키지 1개만 만든다. 예를 들어 Codex가 WP를 수행했다면 Claude 또는 Antigravity 중 하나만 리뷰어가 된다. `ReviewExecutionProtocol.review_work_package()`는 그 리뷰어가 실패했을 때 다른 agent로 fallback할 뿐, Claude와 Agy가 모두 독립적으로 리뷰하는 구조는 아니다.

기획은 "Codex 작업이 끝나면 Claude, Agy가 해당 작업 결과물을 리뷰한다"에 가깝다. 이 경우 리뷰 결과 병합 정책도 필요하다. 예: 한 명이라도 `changes_requested`이면 repair, 모두 approved이면 통과.

권장 수정:

- `PeerReviewPlanner.plan_reviews()`를 WP당 non-owner active agent 전부에 대해 ReviewPackage를 생성하도록 변경한다.
- 단일 active agent일 때만 self-review를 허용한다.
- 같은 WP에 대한 여러 ReviewResult를 병합하는 정책을 명시한다.
- 기존 `prepare_review_repairs()`는 이미 같은 WP의 여러 review result를 batch로 병합하는 코드가 있어 재사용 가능하다.

### 5. 최종 리뷰 수정사항은 자동 중앙 재계획이 아니라 사용자 선택형 post-review queue다

Final review가 `CHANGES_REQUESTED`이면 `finalize_post_review()`가 action item을 만들고 `POST_REVIEW_READY`로 이동한다. 사용자가 `/improve high`, `/improve all`, 특정 item 선택 등을 해야 supplemental WP가 생성된다. 이건 사용자가 말한 "중앙 에이전트가 수정해야 할 사항을 보고한 뒤 work package를 또 만들어 다시 할당"과 절반만 맞다.

현재 장점은 사용자가 최종 리뷰 개선 범위를 선택할 수 있다는 점이다. 그러나 중앙 에이전트가 자동으로 수정 work package DAG를 재작성하는 단계는 없다.

권장 수정:

- final review changes_requested 이후 중앙 에이전트에게 "수정사항을 WP DAG로 변환"하는 synthesis/replanning 단계를 추가한다.
- 사용자에게는 생성된 보강 WP를 보여주고 `Execute` / `보류` / `수정 요청` 버튼을 제공한다.
- 사용자가 명시적으로 선택하는 `/improve` 방식은 고급/수동 모드로 유지한다.

### 6. 실행 단계는 deliberation provider session을 이어받지 않는다

Deliberation과 review 생성 시에는 `provider_sessions=self.workflow.session.provider_sessions`를 넘긴다. 반면 `_start_execution()`은 provider_sessions를 넘기지 않는다. 또한 Codex invoker는 read-only 호출일 때만 `codex exec resume`을 사용한다.

이는 안전한 write 실행을 위해 의도된 선택일 수 있다. 하지만 기획을 "각 agent의 Trinity 세션 하위 provider 대화가 계속 이어짐"으로 엄격하게 보면 execution lane도 별도 session mapping 정책이 필요하다.

권장 수정:

- deliberation session과 execution session을 분리해 저장한다. 예: `codex:read-only`, `codex:workspace-write`.
- workspace-write에서 provider-native resume을 허용할지 provider별 정책으로 결정한다.
- 허용하지 않는다면 UI/문서에 "실행은 설계 세션의 요약과 shared context로 이어지며 provider-native session resume은 read-only에 한정"이라고 명확히 표시한다.

### 7. structured blueprint가 없으면 WP 품질이 약해질 수 있다

model-backed synthesis가 valid `recommended_blueprint.work_packages`를 반환하면 decomposer가 이를 정규화한다. 하지만 비구조화 consensus fallback은 `Consensus Blueprint`만 만들고 `work_packages=[]`가 될 수 있다. 실행 직전 `enable_execution_for_current_blueprint()`에서 decomposer fallback이 동작하지만, 상세한 파일 경계와 dependency는 중앙 모델이 구조화해서 준 경우보다 약해질 수 있다.

권장 수정:

- consensus reached라면 항상 structured blueprint/work_packages가 있어야 한다는 validation을 강화한다.
- fallback heuristic으로 내려간 경우 UI에 "heuristic package graph"임을 표시한다.
- 실행 전 사용자가 blueprint/WP를 확인하고 보강 요청할 수 있게 한다.

## 현재 구현에서 이미 잘 맞는 부분

- Start/Nexus 모두 target agent와 model override를 UI에서 전달한다.
- one-shot provider 호출 후 native session ID와 runtime model metadata를 저장하는 구조가 있다.
- read-only deliberation/review에서는 provider session을 복원해 이어갈 수 있다.
- 중앙 synthesis는 질문, next round prompt, blueprint, work package graph를 산출할 수 있는 schema를 갖고 있다.
- work package는 dependency, expected files, risk, parallelizable, parallel group 정보를 담을 수 있다.
- execute는 target workspace guard와 control repo write guard를 갖고 있다.
- 병렬 실행은 dependency와 file ownership 충돌을 고려한다.
- WP review changes_requested는 자동 repair execution으로 이어진다.
- final review는 codex -> claude -> antigravity fallback 순서를 갖는다.
- final review 후 post-review action item과 supplemental WP로 이어지는 후속 작업 루프가 있다.

## 구현 우선순위 제안

1. 질문 답변 후 `last_target_agents`/`agent_model_overrides` 유지.
2. WP당 모든 non-owner reviewer가 리뷰하도록 PeerReviewPlanner 변경.
3. 여러 WP 리뷰 결과 병합 정책과 UI 표시 강화.
4. final review changes를 중앙 에이전트가 보강 WP DAG로 자동 변환하는 replanning 단계 추가.
5. 중앙 synthesis provider session ID 저장/복원.
6. `next_round_prompt`를 다음 라운드 주요 지시문으로 사용.
7. execution lane provider session 정책을 명확히 결정하고 구현 또는 문서화.

## 결론

현재 Trinity는 사용자가 원하는 end-to-end workflow의 뼈대는 갖추고 있다. 특히 agent 선택, provider session 저장, 중앙 synthesis, work package decomposition, target workspace execution, 자동 WP repair, final review/post-review follow-up은 이미 존재한다.

그러나 기획과 완전히 같다고 보기는 어렵다. 가장 큰 차이는 다음 네 가지다.

1. 질문 답변 후 같은 대상 agent/model로 이어진다는 보장이 부족하다.
2. work package 리뷰가 "다른 모든 에이전트 리뷰"가 아니라 "한 명 리뷰 + fallback"이다.
3. final review 수정사항이 중앙 에이전트의 자동 재계획 WP로 바로 이어지지 않는다.
4. 중앙 에이전트 자체의 provider-native session 지속성이 workflow session에 매핑되어 있지 않다.

따라서 다음 구현 브랜치에서는 이 네 가지를 우선 처리하면 사용자가 기대한 workflow에 가장 크게 가까워진다.
