# Workflow Inspector Projection Cache

## 배경

WorkflowInspector는 각 section의 마지막 텍스트를 저장해 동일 텍스트 update는 생략한다. 하지만 `apply_snapshot()`이 호출될 때마다 progress, current, next, blocked, provider, question, decision, post-review, log section 문자열을 모두 다시 계산한 뒤 section별로 비교한다.

Nexus 화면은 workflow poll 중 동일한 inspector projection을 반복 적용할 수 있으므로, 표시 대상 필드가 같으면 section 계산 자체를 생략하는 것이 낫다.

## 개선 방향

- WorkflowInspector가 화면에 표시하는 필드만 모아 snapshot render key를 만든다.
- render key가 직전 key와 같으면 section 문자열 계산과 update 비교를 모두 생략한다.
- 표시되지 않는 snapshot 필드 변화는 inspector 재계산을 유발하지 않는다.

## 범위

- `src/trinity/textual_app/widgets/inspector.py`
- `tests/test_workflow_inspector_cache.py`

## 검증

- 같은 inspector projection을 다시 적용하면 `_progress_summary()`가 호출되지 않는지 확인한다.
- 표시되는 WP status가 바뀌면 projection 계산이 다시 수행되는지 확인한다.
- WorkflowInspector focused test와 전체 테스트를 통과시킨다.
