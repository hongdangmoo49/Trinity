# Workflow Decomposition Agent Helper

## 목적

`WorkflowEngine`에 남아 있는 decomposition agent 선택 helper를 제거해 agent targeting/spec 필터링 책임을 `WorkflowTargetingFlow`에 모은다.

## 범위

- `WorkflowTargetingFlow.decomposition_agents()`를 추가한다.
- deliberation result, lifecycle, review flow가 work package decomposition/review planning 시 새 helper를 직접 사용한다.
- `WorkflowEngine._decomposition_agents()`를 제거한다.
- 패치 버전을 `1.0.413`으로 올린다.

## 검증

- workflow engine/lifecycle/review focused 테스트를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.413`을 출력해야 한다.
