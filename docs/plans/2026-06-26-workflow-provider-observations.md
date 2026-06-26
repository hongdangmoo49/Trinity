# Workflow Provider Observation Helper 분리

- 브랜치: `refactor/workflow-provider-observations`
- 버전: `1.0.305` -> `1.0.306`
- 대상: `src/trinity/workflow/engine.py`, `src/trinity/workflow/provider_observations.py`

## 배경

`WorkflowEngine`은 deliberation 결과를 받아 workflow 상태를 전이하지만, provider session id, runtime model, resource projection 관찰값을 session에 병합하고 이벤트로 기록하는 세부 로직도 직접 포함하고 있다.

이 로직은 provider runtime metadata를 session state로 반영하는 I/O 경계에 가깝다. 별도 helper로 분리하면 engine은 deliberation 상태 전이에 집중하고, provider observation 정책 변경 범위가 명확해진다.

## 개선안

1. provider session/model/resource projection 관찰값 병합 로직을 `WorkflowProviderObservations`로 이동한다.
2. `WorkflowEngine._record_provider_observations`는 기존 private helper 이름을 유지하되 새 helper로 위임한다.
3. 기존 이벤트명 `provider_metadata_observed`와 payload 구조는 유지한다.
4. workflow engine focused 테스트와 full pytest로 동작 변경이 없음을 확인한다.

## 범위

- provider metadata schema 변경 없음
- provider session/runtime/resource projection key 선정 변경 없음
- deliberation state transition 변경 없음
- public CLI/TUI 동작 변경 없음

## 기대 효과

- provider runtime metadata 반영 정책 변경 시 수정 위치가 명확해진다.
- `WorkflowEngine`에서 provider observation 세부 구현을 제거한다.
- 이후 engine을 얇은 facade로 유지하기 쉬워진다.
