# Nexus Workflow Event Render Window

## 목적

Nexus snapshot 갱신 시 workflow event 문자열을 과도하게 생성하고 화면에 전달하는 비용을 줄인다.

## 범위

- persistence에서 읽는 workflow event tail limit과 UI snapshot에 렌더하는 event line limit을 분리한다.
- 기존 event load tail은 유지해 recovery/last event 계산에 필요한 최근 context를 보존한다.
- `snapshot.workflow_events`에 노출되는 문자열은 별도 render window로 제한하고, 생략 안내 문구는 유지한다.
- 성능 harness와 snapshot 회귀 테스트를 새 render window 기준으로 갱신한다.
- 패치 버전을 `1.0.441`로 올린다.

## 비목표

- persistence event 저장/조회 schema는 변경하지 않는다.
- execution log 80개 window, full execution log modal 동작은 변경하지 않는다.
- report export의 event limit은 변경하지 않는다.

## 검증

- snapshot workflow event window 테스트를 통과해야 한다.
- performance harness가 render window 상한을 검증해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.441`을 출력해야 한다.
