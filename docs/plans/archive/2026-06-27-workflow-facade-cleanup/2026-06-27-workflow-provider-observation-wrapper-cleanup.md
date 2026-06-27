# Workflow Provider Observation Wrapper Cleanup

## 목적

`WorkflowEngine`의 provider observation forwarding wrapper를 제거해 provider 관측값 기록 책임을 `WorkflowProviderObservations`에 모은다.

## 범위

- deliberation 완료 처리에서 provider metadata를 `WorkflowProviderObservations.record_provider_observations()`로 직접 전달한다.
- 테스트도 provider observation flow를 직접 사용하도록 갱신한다.
- `WorkflowEngine._record_provider_observations()`를 제거한다.
- 패치 버전을 `1.0.405`로 올린다.

## 검증

- resource projection metadata persistence 테스트를 통과해야 한다.
- workflow engine focused 테스트를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.405`를 출력해야 한다.
