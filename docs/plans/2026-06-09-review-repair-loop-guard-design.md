# Review Repair Loop Guard 설계

작성일: 2026-06-09  
브랜치: `feature/review-repair-loop-guard-design`  
상태: 설계 및 1차 구현 완료

## 배경

이전 작업이 `main`에 병합된 뒤, 사용자가 기존 워크플로우 `wf-926e6847380d`를 `resume`으로 불러오고 `/execute-retry`를 실행했을 때 Nexus 화면이 심하게 느려지는 문제가 재현되었다.

해당 세션의 현재 상태를 보면 `shared.md` 자체는 이미 작게 유지되고 있었지만, 워크플로우 이벤트와 세션 상태에는 같은 WP에 대한 리뷰-수리 루프가 반복된 흔적이 남아 있었다.

- `WP-002`는 여러 번 `changes_requested` 리뷰를 받았다.
- `work_package_repair_requested` 이벤트가 반복해서 쌓였다.
- 리뷰 수리 요청 직후 같은 WP가 다시 실행 큐에 들어갔다.
- 실행 완료 후 자동 리뷰가 다시 시작되고, 같은 리뷰 결과가 다시 수리 실행을 유발했다.
- `repair_max_attempts` 설정은 존재하지만 실제 리뷰 수리 큐잉 경로에서는 사용되지 않는다.

이 설계의 목표는 리뷰가 필요한 WP를 자동으로 보강하는 흐름은 유지하되, 같은 변경 요청이 무한히 실행을 재시작하거나 UI를 멈추게 하지 않도록 명확한 가드를 추가하는 것이다.

## 구현 메모

2026-06-09에 1차 구현을 진행했다.

- `WorkPackage`에 리뷰 수리 시도 횟수, 마지막 수리 서명, 마지막 리뷰 ID, 차단 이유, 차단 시각을 저장한다.
- `prepare_review_repairs()`가 `max_attempts`를 받도록 변경하고, `TrinityConfig.repair_max_attempts`를 Textual controller에서 전달한다.
- 같은 WP에 같은 `required_changes` 서명이 반복되면 자동 재실행 대신 WP를 `blocked`로 전환한다.
- 최대 자동 수리 횟수를 초과하면 WP를 `blocked`로 전환하고 워크플로우를 `needs_user_decision`으로 바꾼다.
- `work_package_repair_blocked` 이벤트와 `execution_run.state = repair_blocked`를 기록한다.
- 기존 세션을 resume할 때 `work_package_repair_requested` 이벤트를 읽어 새 수리 메타데이터를 복원하고, 이미 최대 시도 횟수 이상 반복된 실행 중 WP는 자동으로 `blocked` 처리한다.
- Nexus snapshot과 `/execute-retry` 모달에 수리 시도 횟수와 차단 이유가 표시되도록 반영했다.
- Local Policy Repairs 표시는 최신 8개로 제한해 과도한 repair note 렌더링을 줄였다.
- Central Agent 영역에 review-repair blocked 전용 버튼을 추가했다.
  - `한 번 더 재시도`: 막힌 WP만 기존 `/execute-retry custom` 경로로 재실행한다.
    - 재시도 큐에 들어간 WP는 화면상 혼동을 피하기 위해 `repair_blocked_reason` 표시를 지운다. 마지막 수리 서명과 시도 횟수는 유지해, 같은 리뷰 변경 요청이 다시 오면 즉시 다시 차단할 수 있다.
  - `완료 처리`: 사용자가 해당 리뷰 수리를 수용한 것으로 보고 WP를 `done` 처리한다.
  - `리뷰 보기`: 현재 review-repair 차단 상세와 최근 repair note를 중앙 영역에 표시한다.
  - `중단`: 현재 워크플로우를 `failed`로 전환하고 repair stop 이벤트를 남긴다.
- Central Agent의 action 버튼은 렌더마다 내부 ID를 고유하게 만들어, 같은 snapshot이 빠르게 다시 적용될 때 Textual `DuplicateIds` 예외가 발생하지 않도록 했다.
- Textual app 레벨에서 review-repair 버튼 라우팅을 검증했다.
  - `리뷰 보기`는 `/review` local command 결과와 표를 중앙 영역에 기록한다.
  - `한 번 더 재시도`는 막힌 WP만 `custom` selector로 `/execute-retry` 흐름에 전달한다.
  - `완료 처리`와 `중단`은 controller의 blocked repair 결정 메서드로 위임한다.

검증:

- `uv run pytest tests/test_workflow_engine.py tests/test_textual_workflow_controller.py -q`: 63 passed
- `uv run pytest tests/test_textual_app.py tests/test_workflow_engine.py tests/test_textual_workflow_controller.py -q`: 155 passed
- `uv run pytest -q`: 1336 passed, 1 existing RuntimeWarning
- Central Agent 버튼 액션 구현 이후 최종 검증:
  - `uv run pytest tests/test_workflow_engine.py tests/test_textual_workflow_controller.py -q`: 70 passed
  - `uv run pytest tests/test_textual_app.py tests/test_workflow_engine.py tests/test_textual_workflow_controller.py -q`: 162 passed
  - `uv run pytest -q`: 1343 passed, 1 existing RuntimeWarning
- Textual app repair action 회귀 테스트 추가 이후 최종 검증:
  - `uv run pytest tests/test_textual_app.py -q`: 96 passed
  - `uv run pytest tests/test_textual_app.py tests/test_workflow_engine.py tests/test_textual_workflow_controller.py -q`: 166 passed
  - `uv run pytest -q`: 1347 passed, 1 existing RuntimeWarning
- Central Agent 버튼 클릭 이벤트 경로 검증 추가 이후 최종 검증:
  - `uv run pytest tests/test_textual_app.py -q`: 97 passed
  - `uv run pytest tests/test_textual_app.py tests/test_workflow_engine.py tests/test_textual_workflow_controller.py -q`: 167 passed
  - `uv run pytest -q`: 1348 passed, 1 existing RuntimeWarning
  - `uv run ruff check .`: 실행 불가. 현재 dev 환경에 `ruff` 실행 파일이 설치되어 있지 않다.
- `/execute-retry custom`이 repair-blocked WP를 다시 pending으로 되돌릴 때, UI 차단 표시는 지우고 수리 시도 횟수와 마지막 수리 서명은 보존하는 단위 테스트를 추가했다.
  - `uv run pytest tests/test_workflow_engine.py -q`: 47 passed
  - `uv run pytest tests/test_textual_app.py tests/test_workflow_engine.py tests/test_textual_workflow_controller.py -q`: 168 passed
  - `uv run pytest -q`: 1349 passed, 1 existing RuntimeWarning
- Snapshot adapter와 `/execute-retry` 모달 표시 테스트를 추가했다.
  - `work_packages` 한 줄 요약에 repair 시도 횟수와 차단 이유가 포함된다.
  - `WorkPackageSnapshot`에 repair 시도/차단 메타데이터가 보존된다.
  - `repair_blocked` execution recovery가 retry 후보로 투영된다.
  - 최근 repair note는 최신 8개만 표시된다.
  - retry modal note는 retry 가능 WP의 repair count/reason과 retry 불가 사유를 구분한다.
  - `uv run pytest tests/test_textual_app.py tests/test_textual_snapshot.py -q`: 119 passed
  - `uv run pytest tests/test_textual_app.py tests/test_textual_snapshot.py tests/test_workflow_engine.py tests/test_textual_workflow_controller.py -q`: 190 passed
  - `uv run pytest -q`: 1351 passed, 1 existing RuntimeWarning
- target workspace가 아직 선택되지 않은 상태에서 `한 번 더 재시도`를 누르는 edge case를 보강했다.
  - App은 blocked WP detail뿐 아니라 `execution_recovery.retry_candidates`에서도 repair retry 대상 WP를 수집한다.
  - workspace picker가 열린 뒤에도 `_pending_execute_retry`에 `custom` selector와 WP 목록이 보존된다.
  - `uv run pytest tests/test_textual_app.py -q`: 100 passed
  - `uv run pytest tests/test_textual_app.py tests/test_textual_snapshot.py tests/test_workflow_engine.py tests/test_textual_workflow_controller.py -q`: 192 passed
  - `uv run pytest -q`: 1353 passed, 1 existing RuntimeWarning
- 한 review batch 안에서 여러 리뷰어가 같은 WP에 `changes_requested`를 반환하는 edge case를 보강했다.
  - `prepare_review_repairs()`는 먼저 WP별 변경 요청을 합친 뒤 package당 한 번만 수리 시도를 계산한다.
  - 같은 WP의 중복 변경 요청은 같은 batch 안에서 즉시 blocked로 바뀌지 않고, 한 번의 retry attempt로 큐잉된다.
  - 같은 WP의 서로 다른 변경 요청도 한 번의 attempt와 하나의 합성 signature로 기록된다.
  - `work_package_repair_requested` 이벤트에는 기존 `review_package_id`와 함께 batch 전체 `review_package_ids`, `reviewers`, `targets`, 병합된 `required_changes`를 기록한다.
  - `uv run pytest tests/test_workflow_engine.py -q`: 49 passed
  - `uv run pytest tests/test_textual_app.py tests/test_textual_snapshot.py tests/test_workflow_engine.py tests/test_textual_workflow_controller.py -q`: 194 passed
  - `uv run pytest -q`: 1355 passed, 1 existing RuntimeWarning
- resume/reconcile 경로가 batch repair 이벤트의 `repair_signature`를 우선 복원하도록 보강했다.
  - 새 batch 이벤트는 병합된 변경 요청으로 만든 signature를 기록하므로, resume 시 마지막 단일 `ReviewResult`로 signature를 재계산하면 기존 batch signature와 어긋날 수 있다.
  - `reconcile_review_repair_metadata()`는 이제 `work_package_repair_requested` 이벤트의 `repair_signature`와 `review_package_id`를 우선 사용하고, 없는 경우에만 기존 review result 기반 계산으로 fallback한다.
  - `uv run pytest tests/test_workflow_engine.py -q`: 50 passed
  - `uv run pytest tests/test_textual_app.py tests/test_textual_snapshot.py tests/test_workflow_engine.py tests/test_textual_workflow_controller.py -q`: 195 passed
  - `uv run pytest -q`: 1356 passed, 1 existing RuntimeWarning
- resume/reconcile 경로가 이벤트 개수뿐 아니라 `repair_attempt_count` 필드를 우선 반영하도록 보강했다.
  - 이벤트 로그가 batch 단위로 기록되거나 일부 이벤트만 남아 있을 때도 실제 attempt count가 낮게 복원되지 않도록 한다.
  - `review_package_id`가 없고 `review_package_ids`만 있는 batch 이벤트는 마지막 review package id를 복원 대상으로 사용한다.
  - `_block_review_repair()`는 빈 `required_changes`와 빈 `review_package_ids`를 명시적으로 전달받아도 fallback으로 오염하지 않도록 처리한다.
  - `uv run pytest tests/test_workflow_engine.py -q`: 51 passed
  - `uv run pytest tests/test_textual_app.py tests/test_textual_snapshot.py tests/test_workflow_engine.py tests/test_textual_workflow_controller.py -q`: 196 passed
  - `uv run pytest -q`: 1357 passed, 1 existing RuntimeWarning
- 같은 review batch에서 일부 WP는 retry 가능하고 일부 WP는 repair guard로 차단되는 mixed 상태를 보강했다.
  - 실행 가능한 WP가 있으면 기존처럼 `retry_requested` run으로 전환한다.
  - 동시에 차단된 WP는 `execution_run.repair_blocked_packages`와 `execution_recovery_action.blocked_packages`에 남긴다.
  - 이렇게 하면 실행은 계속 진행하되, inspector/snapshot/recovery 경로에서 차단된 WP가 사라지지 않는다.
  - `uv run pytest tests/test_workflow_engine.py -q`: 52 passed
  - `uv run pytest tests/test_textual_app.py tests/test_textual_snapshot.py tests/test_workflow_engine.py tests/test_textual_workflow_controller.py -q`: 197 passed
  - `uv run pytest -q`: 1358 passed, 1 existing RuntimeWarning
- recovery-only `repair_blocked` snapshot에서 `리뷰 보기`가 비어 보이지 않도록 보강했다.
  - 상세 WP snapshot이 없어도 `execution_recovery.retry_candidates`를 fallback row로 표시한다.
  - `uv run pytest tests/test_textual_app.py -q`: 101 passed
  - `uv run pytest tests/test_textual_app.py tests/test_textual_snapshot.py tests/test_workflow_engine.py tests/test_textual_workflow_controller.py -q`: 198 passed
  - `uv run pytest -q`: 1359 passed, 1 existing RuntimeWarning
- mixed `retry_requested` 상태에서 blocked WP가 snapshot에 계속 보이는지 검증했다.
  - `retry_requested`는 recovery panel로 투영하지 않지만, `work_packages`, `work_package_details`, `work_package_repairs`에 retry/blocked 메타데이터를 유지한다.
  - `uv run pytest tests/test_textual_snapshot.py -q`: 22 passed
  - `uv run pytest tests/test_textual_app.py tests/test_textual_snapshot.py tests/test_workflow_engine.py tests/test_textual_workflow_controller.py -q`: 199 passed
  - `uv run pytest -q`: 1360 passed, 1 existing RuntimeWarning
- mixed repair 상태에서 controller 메시지와 실행 run metadata 승계를 보강했다.
  - `begin_execution()`은 `retry_requested` run에서 `repair_blocked_packages`와 `repair_blocked_at`을 running run으로 이어받는다.
  - Textual controller는 일부 WP가 retry되고 일부 WP가 guard로 차단되면 메시지에 `Blocked by repair guard: ...`를 함께 표시한다.
  - `uv run pytest tests/test_textual_workflow_controller.py -q`: 25 passed
  - `uv run pytest tests/test_textual_app.py tests/test_textual_snapshot.py tests/test_workflow_engine.py tests/test_textual_workflow_controller.py -q`: 200 passed
  - `uv run pytest -q`: 1361 passed, 1 existing RuntimeWarning
- Central Agent repair action 노출 조건을 좁혔다.
  - `repair_blocked` recovery 상태이거나 workflow가 `needs_user_decision`일 때만 repair decision 버튼을 보여준다.
  - mixed retry/executing 상태에서는 blocked WP 정보는 snapshot에 남기되, 실행 중 화면을 repair decision 버튼으로 덮지 않는다.
  - `uv run pytest tests/test_textual_workflow_controller.py -q`: 26 passed
  - `uv run pytest tests/test_textual_app.py tests/test_textual_snapshot.py tests/test_workflow_engine.py tests/test_textual_workflow_controller.py -q`: 201 passed
  - `uv run pytest -q`: 1362 passed, 1 existing RuntimeWarning
- review repair restart가 실제 execution worker를 시작하지 못하는 edge case를 보강했다.
  - `_start_execution()`은 이제 실제 worker 시작 여부를 bool로 반환한다.
  - review repair가 pending WP를 만들었지만 target workspace가 없으면 controller가 running 상태로 가장하지 않고 `target_workspace_required=True`를 반환한다.
  - App polling은 `drain_updates()` 결과의 `target_workspace_required`를 처리해 workspace picker를 연다.
  - `uv run pytest tests/test_textual_workflow_controller.py tests/test_textual_app.py -q`: 129 passed
  - `uv run pytest tests/test_textual_app.py tests/test_textual_snapshot.py tests/test_workflow_engine.py tests/test_textual_workflow_controller.py -q`: 203 passed
  - `uv run pytest -q`: 1364 passed, 1 existing RuntimeWarning
- target workspace 선택 후 pending review-repair 실행을 이어가는 경로를 보강했다.
  - review repair가 이미 `retry_requested` run과 pending WP를 만든 경우, 이후 `/execute`/workspace picker continuation은 blueprint 전체를 재-enable하지 않고 pending review-repair packages만 실행한다.
  - `uv run pytest tests/test_textual_workflow_controller.py -q`: 28 passed
  - `uv run pytest tests/test_textual_app.py tests/test_textual_snapshot.py tests/test_workflow_engine.py tests/test_textual_workflow_controller.py -q`: 204 passed
  - `uv run pytest -q`: 1365 passed, 1 existing RuntimeWarning
- execution start outcome 신호를 실제 worker 시작 여부에 맞게 보정했다.
  - `_apply_action()`과 `confirm_execution_retry()`는 `_start_execution()` 반환값을 사용해 `execution_requested`와 `running`을 설정한다.
  - 실행이 실제로 시작되지 않았는데 UI가 execution requested 상태로 오해하는 것을 막는다.
  - `uv run pytest tests/test_textual_workflow_controller.py -q`: 28 passed
  - `uv run pytest tests/test_textual_app.py tests/test_textual_snapshot.py tests/test_workflow_engine.py tests/test_textual_workflow_controller.py -q`: 204 passed
  - `uv run pytest -q`: 1365 passed, 1 existing RuntimeWarning

## 관찰된 증거

`wf-926e6847380d` 세션에서 확인한 주요 지표는 다음과 같다.

- 워크플로우 상태: `executing`
- 라운드: `1`
- WP 상태: `done` 2개, `running` 1개
- 리뷰 결과: 20개 내외까지 누적
- `WP-002`의 `changes_requested` 리뷰가 반복 누적
- `WP-002`의 `repair_notes`가 18개 수준으로 누적
- 실행 중인 하위 프로세스가 `codex exec ...` 형태로 다시 떠 있었다.

현재 `.trinity/shared.md`는 약 4KB 수준이라 직접적인 원인으로 보기 어렵다. 다만 `.trinity/shared.md.oversized-*` 형태의 대형 백업 파일이 남아 있었고, 이후 별도 정리 정책의 후보가 될 수 있다.

## 현재 코드 흐름

### 자동 리뷰 후 수리 재실행

[src/trinity/textual_app/workflow_controller.py](/home/user/workspace/Trinity/src/trinity/textual_app/workflow_controller.py:391)

`TextualWorkflowController.drain_updates()`는 실행이 끝난 뒤 자동 리뷰를 시작하고, 리뷰가 끝난 뒤 변경 요청이 있으면 다시 실행을 시작한다.

현재 흐름은 다음과 같다.

1. `run_kind == "execution"` 완료
2. `record_execution_results()`
3. `_should_auto_review_after_execution()`이 참이면 `_start_review()`
4. `run_kind == "review"` 완료
5. `record_review_results()`
6. `prepare_review_repairs(review_results)`
7. 반환된 WP가 있으면 `_start_execution()`

문제는 6번에서 같은 변경 요청인지, 이미 충분히 재시도했는지, 사용자의 판단이 필요한 상태인지 확인하지 않고 같은 WP를 다시 실행한다는 점이다.

### 리뷰 수리 큐잉

[src/trinity/workflow/engine.py](/home/user/workspace/Trinity/src/trinity/workflow/engine.py:1118)

`WorkflowEngine.prepare_review_repairs()`는 `ReviewStatus.CHANGES_REQUESTED`인 결과를 만나면 해당 WP를 바로 `PENDING`으로 되돌리고 `execution_run.retry_selector = "review-repair"`로 설정한다.

현재 누락된 가드는 다음과 같다.

- `repair_max_attempts` 사용
- 같은 `required_changes` 반복 감지
- 리뷰 결과 중복 기록 감지
- 이미 `repair_notes`에 반영된 변경 요청인지 확인
- 자동 재실행이 아니라 사용자 결정을 요구해야 하는 상태 구분

### 리뷰 결과 기록

[src/trinity/workflow/engine.py](/home/user/workspace/Trinity/src/trinity/workflow/engine.py:1176)

`_record_review_result()`는 모든 리뷰 결과를 `session.review_results`에 계속 append한다. 중복 리뷰 결과라도 별도의 압축이나 최신 N개 제한 없이 세션 JSON에 누적된다.

[src/trinity/workflow/engine.py](/home/user/workspace/Trinity/src/trinity/workflow/engine.py:1193)

`_apply_review_result_to_package()`는 `changes_requested`일 때 WP 상태를 `NEEDS_REVIEW`로 바꾸고 `repair_notes`를 추가한다. 동일 note 문자열은 중복 추가하지 않지만, 이후 `prepare_review_repairs()`가 여전히 WP를 실행 큐에 넣을 수 있다.

### 설정은 있으나 연결되지 않음

[src/trinity/config.py](/home/user/workspace/Trinity/src/trinity/config.py:88)

`repair_max_attempts: int = 3` 설정이 이미 존재한다. 설정 로딩과 저장 테스트도 있다. 그러나 현재 리뷰 수리 루프에는 이 값이 전달되지 않는다.

## 문제 정의

이번 작업에서 해결해야 하는 문제는 네 가지다.

1. 같은 WP가 동일한 리뷰 변경 요청으로 계속 재실행된다.
2. 자동 리뷰와 자동 수리가 연쇄되어 사용자가 제어권을 되찾기 어렵다.
3. 세션 JSON과 UI 렌더링 대상이 계속 커져 Nexus 화면이 느려질 수 있다.
4. `resume` 후 기존 이벤트를 기준으로 이미 반복 루프에 빠진 세션을 안전하게 멈추는 장치가 없다.

## 설계 목표

- 자동 리뷰 수리 루프는 반드시 유한해야 한다.
- 같은 변경 요청이 반복되면 추가 실행 대신 사용자 결정 상태로 전환한다.
- `repair_max_attempts` 설정을 실제 리뷰 수리 큐잉 정책에 연결한다.
- `/execute-retry`는 사용자가 명시적으로 고른 WP만 재시도하되, 기존 리뷰 수리 가드를 무시하지 않는다.
- UI는 리뷰/수리 이력이 많아도 최신 항목 중심으로 빠르게 렌더링한다.
- 기존 세션을 `resume`했을 때도 반복 루프를 감지하고 중단할 수 있어야 한다.

## 데이터 모델 변경안

`WorkPackage`에 리뷰 수리 메타데이터를 추가한다.

```python
repair_attempt_count: int = 0
last_repair_signature: str = ""
last_repair_review_id: str = ""
repair_blocked_reason: str = ""
repair_blocked_at: float = 0.0
```

각 필드는 다음 의미를 가진다.

- `repair_attempt_count`: 리뷰 변경 요청으로 자동 재실행된 횟수
- `last_repair_signature`: 마지막으로 자동 수리를 유발한 변경 요청의 정규화 서명
- `last_repair_review_id`: 마지막 수리 요청을 만든 리뷰 패키지 ID
- `repair_blocked_reason`: 중복 요청이나 최대 재시도 초과로 자동 수리가 멈춘 이유
- `repair_blocked_at`: 자동 수리가 멈춘 시각

`to_dict()`와 `from_dict()`에 필드를 추가하고, 기존 세션에는 안전한 기본값을 사용한다.

## 변경 요청 서명

리뷰 변경 요청이 같은 내용인지 판단하기 위해 정규화된 서명을 만든다.

```python
payload = {
    "package_id": result.package_id,
    "target_agent": result.target_agent,
    "required_changes": sorted(normalize(change) for change in result.required_changes),
}
signature = sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
```

서명에는 `reviewer_agent`를 넣지 않는 것을 기본안으로 둔다. 같은 변경 요청이 다른 리뷰어에게서 반복되어도 같은 수리 요구로 보는 편이 무한 루프를 더 잘 막기 때문이다.

정규화 규칙은 다음 정도로 시작한다.

- 앞뒤 공백 제거
- 연속 공백을 하나로 축약
- 비어 있는 항목 제거
- 대소문자 구분이 의미 없는 영어 문장은 lower 처리 검토

한글 요구사항은 대소문자 처리 영향이 없으므로 그대로 유지한다.

## 수리 큐잉 정책

`prepare_review_repairs()`는 단순히 `tuple[str, ...]`만 반환하지 말고, 내부적으로 수리 결정 결과를 만들 수 있어야 한다. 최소 구현은 반환 타입을 유지하되, 이벤트와 WP 필드에 결정 이유를 기록하는 방식으로 시작할 수 있다.

권장 흐름은 다음과 같다.

1. `changes_requested` 결과만 대상으로 한다.
2. 최종 리뷰(`FINAL`)는 자동 WP 수리 대상에서 제외한다.
3. 실행이 필요 없는 WP는 제외한다.
4. 변경 요청 서명을 계산한다.
5. `repair_attempt_count >= repair_max_attempts`이면 자동 수리를 막는다.
6. `last_repair_signature == signature`이고 새 변경사항이 없으면 자동 수리를 막는다.
7. 자동 수리가 허용되면 `repair_attempt_count += 1`을 기록하고 WP를 `PENDING`으로 전환한다.
8. 막힌 WP가 하나 이상 있고 실행 대상이 없으면 워크플로우를 `NEEDS_USER_DECISION`으로 전환한다.

자동 수리가 막혔을 때 기록할 이벤트는 다음과 같다.

```json
{
  "type": "work_package_repair_blocked",
  "package_id": "WP-002",
  "reason": "duplicate_required_changes",
  "attempt_count": 3,
  "max_attempts": 3,
  "review_package_id": "RP-WP-002-antigravity"
}
```

가능한 `reason` 값은 다음과 같이 둔다.

- `duplicate_required_changes`
- `max_attempts_exceeded`
- `package_not_executable`
- `review_scope_not_repairable`

## 설정 연결

`TextualWorkflowController`는 `prepare_review_repairs()`를 호출할 때 `self.config.repair_max_attempts`를 전달해야 한다.

```python
repair_packages = self.workflow.prepare_review_repairs(
    review_results,
    max_attempts=self.config.repair_max_attempts,
)
```

`WorkflowEngine.prepare_review_repairs()`의 기본값은 3으로 두어 CLI/TUI 테스트와 직접 호출에서도 안정적으로 동작하게 한다.

## 상태 전환

자동 수리 대상이 있을 때:

- WP 상태: `PENDING`
- Workflow 상태: `BLUEPRINT_READY`
- `execution_run.retry_selector`: `review-repair`
- Controller: `_start_execution()`

자동 수리가 막혔고 사용자 판단이 필요할 때:

- WP 상태: `WAITING_ON_DECISION` 또는 `NEEDS_REVIEW`
- Workflow 상태: `NEEDS_USER_DECISION`
- Central Agent 영역에 결정 질문 표시
- Controller: 새 background execution을 시작하지 않음

질문 예시는 다음과 같다.

```text
WP-002가 같은 리뷰 변경 요청으로 3회 반복되었습니다. 어떻게 처리할까요?
```

버튼 옵션:

- `한 번 더 재시도`
- `완료로 표시`
- `리뷰 상세 보기`
- `중단`

## `/execute-retry`와의 관계

`/execute-retry`는 사용자가 명시적으로 고른 WP를 재시도하는 명령이다. 그러나 리뷰 수리 루프에서 막힌 WP를 다시 실행할 때도 다음 정책을 적용한다.

- 기본적으로 `repair_attempt_count`를 초기화하지 않는다.
- 사용자가 명시적으로 `한 번 더 재시도`를 선택했을 때만 1회성 override를 허용한다.
- override 실행 후 같은 서명이 다시 나오면 즉시 `NEEDS_USER_DECISION`으로 돌아간다.

향후 옵션으로 다음 플래그를 추가할 수 있다.

```text
/execute-retry --reset-repair-attempts
```

다만 UI 모달에서 먼저 제공하는 것이 좋다. CLI 플래그는 보조 경로로 둔다.

## Resume 처리

기존 세션에는 새 필드가 없을 수 있다. 따라서 resume 시 다음 보정이 필요하다.

1. `WorkPackage.from_dict()`는 새 필드가 없어도 기본값으로 로딩한다.
2. 가능하면 `events.jsonl`의 `work_package_repair_requested`와 `work_package_repair_blocked`를 읽어 `repair_attempt_count`를 복원한다.
3. 이미 같은 WP에 3회 이상 수리 요청이 있으면 자동 실행 재개 대신 `NEEDS_USER_DECISION`으로 전환한다.
4. `execution_run.state == "running"`인데 하위 프로세스가 없으면 기존 recovery 흐름처럼 interrupted 후보로 표시한다.

`wf-926e6847380d` 같은 기존 세션은 resume 직후 자동으로 새로운 `codex exec`가 뜨지 않아야 한다. 먼저 중앙 영역에 반복 수리 감지 메시지와 선택지를 보여주는 것이 목표다.

## UI 설계

### Central Agent

Central Agent에는 현재 WP 수리 상태를 사람이 이해할 수 있게 보여준다.

예시:

```text
Review repair paused
WP-002 has repeated the same required changes.
Attempt: 3 / 3
Reason: duplicate required changes
```

아래에는 버튼을 제공한다.

- `Retry once`
- `Mark done`
- `Open review`
- `Stop`

한글 UI에서는 다음과 같이 번역한다.

- `한 번 더 재시도`
- `완료 처리`
- `리뷰 보기`
- `중단`

### Inspector

Inspector는 리뷰/수리 이력이 많아도 전체를 전부 렌더링하지 않는다.

- WP별 리뷰 결과는 최신 3개만 기본 표시
- 총 개수는 `20 total, showing latest 3` 형태로 표시
- `repair_notes`는 최신 5개만 기본 표시
- 상세 모달 또는 명령으로 전체를 볼 수 있게 확장 가능

### Execution Retry Modal

`/execute-retry` 모달의 WP 목록에 다음 정보를 추가한다.

- `repair_attempt_count / repair_max_attempts`
- `repair_blocked_reason`
- 마지막 리뷰어
- 마지막 required changes 요약

blocked/interrupted 필터에서는 리뷰 수리로 막힌 WP도 명확히 선택 가능해야 한다.

## 세션 파일 크기 관리

이번 설계의 1차 범위는 무한 루프 차단이다. 다만 UI 지연을 줄이기 위해 다음도 함께 고려한다.

- `session.review_results`는 계속 저장하되 UI는 최신 N개만 렌더링한다.
- 장기적으로는 리뷰 결과도 이벤트 로그 기반 요약과 원본 artifact 경로로 분리할 수 있다.
- `.trinity/shared.md.oversized-*` 백업 파일은 현재 루프 원인은 아니지만, `/memory compact`나 cleanup 명령에서 정리 후보로 표시할 수 있다.

## 구현 단계

### 1단계: 루프 차단 핵심

- `WorkPackage`에 수리 메타데이터 필드 추가
- 변경 요청 서명 함수 추가
- `prepare_review_repairs()`에 `max_attempts` 인자 추가
- 중복 변경 요청과 최대 재시도 초과를 감지
- 막힌 경우 `work_package_repair_blocked` 이벤트 기록
- Controller에서 `config.repair_max_attempts` 전달

### 2단계: 사용자 결정 흐름

- 수리 blocked 상태일 때 Workflow를 `NEEDS_USER_DECISION`으로 전환
- Central Agent에 질문과 버튼 표시
- `Retry once`, `Mark done`, `Open review`, `Stop` 액션 처리

### 3단계: Resume 안전장치

- resume 시 기존 이벤트에서 수리 반복 횟수 추론
- 반복 루프가 이미 감지된 세션은 자동 실행하지 않음
- `execution_run` 상태와 실제 하위 프로세스 상태가 다르면 interrupted/retry 후보로 분리

### 4단계: UI 렌더링 제한

- Inspector 리뷰 결과 최신 N개 표시
- repair notes 최신 N개 표시
- 전체 이력은 별도 상세 모달 또는 artifact 경로로 접근

## 테스트 계획

### 단위 테스트

`tests/test_workflow_engine.py`

- 첫 `changes_requested`는 WP를 `PENDING`으로 큐잉한다.
- 같은 `required_changes`가 반복되면 두 번째 자동 수리는 막힌다.
- `repair_max_attempts`를 초과하면 자동 수리는 막힌다.
- 다른 `required_changes`는 제한 횟수 안에서 수리 큐잉할 수 있다.
- 최종 리뷰(`FINAL`)는 WP 수리 큐잉 대상이 아니다.
- 새 `WorkPackage` 필드는 `to_dict()` / `from_dict()`에서 round-trip 된다.

`tests/test_textual_workflow_controller.py`

- 리뷰 완료 후 수리 대상이 있으면 `_start_execution()`이 호출된다.
- 중복 변경 요청으로 수리 대상이 없으면 `_start_execution()`이 호출되지 않는다.
- Controller가 `config.repair_max_attempts`를 `prepare_review_repairs()`로 전달한다.

### 회귀 테스트

`wf-926e6847380d`와 비슷한 fixture를 만든다.

- 동일 WP에 `work_package_repair_requested`가 3회 이상 있다.
- resume 후 `/execute-retry`를 해도 즉시 새 자동 review-repair 루프로 들어가지 않는다.
- Central Agent가 사용자 결정을 요구한다.

### UI 테스트

`tests/test_textual_app.py`

- Central Agent가 blocked repair 상태를 표시한다.
- 질문 버튼이 표시되고 잘리지 않는다.
- Inspector는 리뷰 결과가 20개 이상이어도 최신 일부만 표시한다.
- `/execute-retry` 모달에 수리 시도 횟수와 blocked 이유가 표시된다.

## 수용 기준

- 한 WP는 같은 리뷰 변경 요청으로 무한히 재실행되지 않는다.
- `repair_max_attempts = 3`이면 자동 리뷰 수리 실행은 최대 3회로 제한된다.
- 동일 변경 요청이 반복되면 자동 실행 대신 `NEEDS_USER_DECISION`으로 전환된다.
- `resume + /execute-retry`가 기존 반복 루프를 다시 폭주시켜서는 안 된다.
- 리뷰 결과가 20개 이상인 세션에서도 Nexus/Inspector 화면이 응답성을 유지한다.
- 기존 세션 JSON은 새 필드가 없어도 정상 로딩된다.

## 비범위

- 리뷰어 품질 자체를 개선하는 프롬프트 튜닝
- provider별 모델 선택 UI
- shared memory 전체 재설계
- 대형 backup 파일 자동 삭제 정책
- 최종 리뷰 fallback 순서 변경

위 항목은 관련은 있지만 이번 작업의 핵심 원인 제거 이후 별도 브랜치에서 다루는 것이 좋다.
