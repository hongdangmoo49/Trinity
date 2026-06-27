# Textual Route Snapshot Applier

## 목적

`TrinityTextualApp`에 남아 있는 route별 snapshot 재적용 분기를 작은 helper로 분리해 화면 전환 책임을 줄인다.

## 범위

- `WorkbenchRoute` 타입과 현재 route snapshot 적용 함수를 별도 모듈로 옮긴다.
- Nexus, Execution Matrix, Report 화면에 snapshot을 재적용하는 분기를 helper에서 처리한다.
- `TrinityTextualApp._refresh_current_route_from_active_snapshot()`은 snapshot 조회와 helper 호출만 담당한다.
- route 전환 순서, report structured render, execution preflight 정책은 변경하지 않는다.
- 패치 버전을 `1.0.424`로 올린다.

## 비목표

- `switch_to()` 전체를 분리하지 않는다.
- workspace picker나 target workspace 정책은 변경하지 않는다.
- 화면 레이아웃과 렌더링 캐시는 변경하지 않는다.

## 검증

- route snapshot helper focused test를 추가한다.
- Textual app route 관련 focused test를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.424`를 출력해야 한다.
