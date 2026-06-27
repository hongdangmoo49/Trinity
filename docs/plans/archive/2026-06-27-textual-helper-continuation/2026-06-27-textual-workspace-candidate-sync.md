# Textual Workspace Candidate Sync

## 목적

`TrinityTextualApp`에 흩어진 workspace candidate 할당과 Start/Nexus 화면 동기화 호출을 내부 helper로 모아 workspace 흐름의 책임을 줄인다.

## 범위

- `_set_workspace_candidate()` helper를 추가해 앱 상태 갱신, Start 화면 반영, Nexus 화면 반영 옵션을 한곳에서 처리한다.
- Start 화면 submit, workspace picker candidate 선택, Nexus workspace 선택, target workspace 설정 완료 지점이 helper를 사용하게 정리한다.
- 기존 동기화 순서와 화면 반영 범위는 유지한다.
- 패치 버전을 `1.0.433`으로 올린다.

## 비목표

- workspace picker UI, target preparation, control repo confirmation 정책은 변경하지 않는다.
- candidate 값의 resolve 정책은 변경하지 않는다.

## 검증

- workspace/target 관련 Textual app focused test를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.433`을 출력해야 한다.
