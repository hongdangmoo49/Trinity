# Textual Snapshot Source

## 목적

`TrinityTextualApp`에 남아 있는 active/controller/persisted snapshot 선택 우선순위를 helper로 분리해 route와 command handler가 같은 기준을 재사용할 수 있게 한다.

## 범위

- current snapshot 선택은 기존처럼 active snapshot을 먼저 사용하고, 없을 때 controller snapshot, persisted snapshot 순서로 조회한다.
- fresh snapshot 선택은 기존처럼 active snapshot을 무시하고 controller snapshot, persisted snapshot 순서로 조회한다.
- loader는 lazy 호출을 유지해 active snapshot이 있을 때 불필요한 controller/persisted 조회를 하지 않는다.
- route refresh의 중복 snapshot 선택도 같은 helper를 사용하게 정리한다.
- 패치 버전을 `1.0.427`로 올린다.

## 비목표

- snapshot adapter나 workflow controller의 snapshot 생성 방식은 변경하지 않는다.
- local command 결과 병합이나 route 렌더링 정책은 변경하지 않는다.

## 검증

- snapshot source helper focused test를 추가한다.
- Textual app route/status 관련 focused test를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.427`을 출력해야 한다.
