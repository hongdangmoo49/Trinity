# Nexus Review UI Performance

작성일: 2026-06-12

브랜치: `codex/nexus-review-ui-performance`

상태: 구현 반영

## 배경

리뷰 단계가 길어지면 사용자가 두 곳에서 느림을 체감한다.

1. Execution 페이지에서 Nexus 페이지로 이동할 때 전환이 무겁다.
2. Nexus 페이지에서 Central Agent 영역의 누적 내용을 볼 때 화면이 느리다.

직접 확인한 현재 세션 기준 수치는 다음과 같다.

- `.trinity/workflow/session.json`: 약 426KB
- `review_results`: 38개, 약 170KB
- `events.jsonl`: 170줄, 약 108KB
- `NexusSnapshotAdapter.load_snapshot()`: 약 18~20ms
- Central Agent Markdown 본문: 약 33KB, 408줄

따라서 병목은 세션 파일 읽기 하나가 아니라, `snapshot -> Nexus 전체 apply -> Central Markdown 전체
재파싱/렌더 -> 테이블/버튼 재마운트`가 반복되는 구조에 있다.

## 현재 원인

### Nexus 전환 중복 렌더

`TrinityTextualApp.switch_to("nexus")`는 화면 전환 전에 `nexus.apply_snapshot()`을 호출한다.
그 후 `switch_screen()`을 호출하고, `active_snapshot`이 있으면 `call_after_refresh()`에서 다시
현재 route에 snapshot을 적용한다.

즉 Nexus 진입 시 같은 snapshot이 최소 두 번 렌더될 수 있다.

### 숨은 Nexus 업데이트

실행/리뷰 중에는 `0.25`초마다 workflow controller를 폴링한다. 새 이벤트가 있으면 현재 route가
Execution이어도 `_apply_workflow_outcome()`이 Nexus 화면에 snapshot을 적용한다.

사용자가 보지 않는 Nexus 화면까지 계속 갱신되므로, 리뷰가 길수록 UI 스레드가 불필요한 렌더링을
수행한다.

### Central Agent 전체 Markdown 렌더

`CentralAgentView.apply_snapshot()`은 매번 `_markdown()` 전체 문자열을 만들고 `Markdown.update()`로
통째로 갈아끼운다. `_markdown()`에는 goal, synthesis, blueprint, WP graph, execution summary,
local command results, final review, post-review items, decisions, subtasks, repair notes가 누적된다.

또 local command table과 action/question button 영역도 매번 `remove_children()` 후 다시 mount한다.

### Provider panel raw 출력 표시

`NexusScreen.apply_snapshot()`은 provider panel에 `raw_output`을 `details`로 전달한다. Provider panel은
`details or summary`를 표시하므로, provider 출력이 커지면 Nexus 상단 패널도 불필요하게 커진다.

원문은 Provider Inspector에서만 필요하다.

### Review 컬럼의 중간 상태 부재

Execution Matrix의 `Review` 컬럼은 `review_results`가 기록된 뒤에만 값을 표시한다. 리뷰 패키지가
계획되었거나 실행 중인 동안은 `-`로 보이므로, `state_changed: reviewing`과 상단 표가 서로 모순처럼
보인다.

## 목표

- Nexus 페이지 전환 시 같은 snapshot을 중복 적용하지 않는다.
- 현재 보이지 않는 Nexus 화면에는 무거운 central render를 하지 않는다.
- Central Agent가 동일한 snapshot 내용으로 반복 렌더하지 않도록 한다.
- Provider panel에는 짧은 summary만 표시하고 raw output은 inspector에 남긴다.
- Review 컬럼은 `queued`, `reviewing`, 최종 결과 상태를 구분해서 표시한다.
- 기존 workflow, execution, review 동작은 변경하지 않는다.

## 비목표

- Textual route 구조를 전면 교체하지 않는다.
- 세션 저장 포맷을 마이그레이션하지 않는다.
- 리뷰 실행 정책, repair 정책, provider 호출 방식은 바꾸지 않는다.
- Central Agent를 완전한 가상 스크롤 로그로 재작성하지 않는다.

## UX 계약

### Nexus 전환

- Nexus로 이동할 때 snapshot 적용은 한 번만 일어난다.
- 화면 전환 후 최신 active snapshot이 보인다.
- 실행/리뷰가 백그라운드에서 돌고 있어도 현재 보이지 않는 Nexus의 heavy render는 생략한다.

### Central Agent

- 내용이 바뀌지 않은 snapshot에 대해서는 Markdown/table/button을 다시 그리지 않는다.
- activity spinner처럼 title만 바뀌는 경우에는 title만 갱신한다.
- local command table은 local command 결과가 바뀐 경우에만 재마운트한다.
- 질문/액션 버튼은 질문/상태/action set이 바뀐 경우에만 재마운트한다.

### Provider panel

- provider panel summary 영역에는 `summary`만 보여준다.
- `raw_output`은 Provider Inspector에서 계속 확인할 수 있다.
- summary가 없으면 기존처럼 "No response yet"를 표시한다.

### Review 컬럼

- 리뷰 패키지가 없고 결과도 없으면 `-`.
- 리뷰 패키지가 계획되었고 결과가 없으면 `queued`.
- 워크플로우 상태가 `reviewing`이고 해당 리뷰 결과가 없으면 `reviewing`.
- 결과가 있으면 `approved`, `changes_requested`, `blocked`, `failed` 등 실제 결과를 표시한다.
- 같은 WP에 리뷰어가 여러 명이면 가장 보수적인 집계 상태를 표시한다.

집계 우선순위:

1. `failed`
2. `blocked`
3. `changes_requested`
4. `approved`
5. `reviewing`
6. `queued`

단, 계획된 리뷰어 중 일부만 `approved`를 반환했고 아직 남은 리뷰어가 있으면 `approved`로 확정하지
않고 `reviewing` 또는 `queued`를 유지한다.

## 구현 계획

1. `TrinityTextualApp.switch_to()`에서 route 전환 전 snapshot apply를 제거하고, 전환 후 한 번만 적용한다.
2. `_apply_workflow_outcome()`은 현재 route가 Nexus일 때만 `NexusScreen.apply_snapshot()`을 호출한다.
3. `CentralAgentView`에 markdown/local command/action/question render key를 추가해 동일 내용 재렌더를 막는다.
4. `NexusScreen.apply_snapshot()`에서 provider panel에는 `summary`만 전달하고 raw output은 snapshot에 유지한다.
5. `NexusSnapshotAdapter`에서 planned review package와 review result를 집계해 `WorkPackageSnapshot.review_status`에 중간 상태를 넣는다.
6. 관련 Textual/snapshot 테스트를 추가한다.

## 테스트 기준

- Nexus가 현재 route가 아닐 때 workflow outcome을 받아도 Central Agent render가 호출되지 않는다.
- Nexus로 전환할 때 동일 snapshot apply가 중복 호출되지 않는다.
- CentralAgentView에 같은 snapshot을 두 번 적용하면 Markdown update와 table remount가 반복되지 않는다.
- Provider panel은 raw output 대신 summary를 표시하고, Provider Inspector는 raw output을 계속 표시한다.
- Review 결과가 없는 planned review package는 `queued` 또는 `reviewing`으로 표시된다.
- 여러 리뷰 결과가 있으면 보수적 집계 상태가 표시된다.
- 기존 Execution Matrix, Provider Inspector, slash command UI 테스트가 통과한다.

## 구현 결과

- `NexusSnapshotAdapter`가 `review_packages`와 `review_results`를 함께 읽어 WP별 review projection을 만든다.
- 리뷰 결과가 아직 없지만 리뷰 패키지가 있으면 `queued`/`reviewing`을 표시한다.
- 여러 리뷰어 결과가 있으면 `failed > blocked > changes_requested > approved` 순으로 보수적으로 집계한다.
- Nexus가 현재 route가 아닐 때 `_apply_workflow_outcome()`이 `NexusScreen.apply_snapshot()`을 호출하지 않는다.
- Nexus 전환 시 route 전환 전 선행 apply를 제거하고, 전환 후 refresh에서 한 번만 snapshot을 적용한다.
- `CentralAgentView`는 Markdown, local command table, action buttons, question buttons의 render key를 보관해 동일 내용 재렌더를 생략한다.
- Provider panel은 raw output 대신 summary만 표시한다. raw output은 Provider Inspector에서 계속 볼 수 있다.

## 집중 검증

```text
uv run pytest tests/test_textual_snapshot.py::test_snapshot_projects_planned_review_as_reviewing tests/test_textual_snapshot.py::test_snapshot_projects_planned_review_as_queued_before_reviewing tests/test_textual_snapshot.py::test_snapshot_aggregates_multiple_work_package_review_results tests/test_textual_app.py::test_workflow_outcome_does_not_render_hidden_nexus tests/test_textual_app.py::test_switch_to_nexus_applies_snapshot_once tests/test_textual_app.py::test_central_agent_view_skips_repeated_snapshot_rerender tests/test_textual_app.py::test_provider_panel_shows_summary_and_keeps_raw_in_inspector -q
```

결과:

```text
7 passed in 5.17s
```
