# Textual Local Command Presenter

## 목적

`TrinityTextualApp`에 남아 있는 local command 결과 작성 로직을 pure presenter 함수로 옮겨 UI 상태 변경과 표시 데이터 생성을 분리한다.

## 범위

- local command 결과를 `LocalCommandSnapshot`으로 만드는 presenter 함수를 추가한다.
- `/status` 결과 생성도 동일한 presenter 경로를 사용하게 정리한다.
- `TrinityTextualApp`은 생성된 결과를 저장하고 화면에 반영하는 역할만 유지한다.
- 기존 modal, notify, snapshot 적용 동작은 변경하지 않는다.
- 패치 버전을 `1.0.421`로 올린다.

## 비목표

- Nexus 화면 배치나 위젯 렌더링 정책은 변경하지 않는다.
- slash command 라우팅과 workflow snapshot 구조는 변경하지 않는다.

## 검증

- local command/status presenter 단위 테스트를 추가하거나 기존 테스트를 보강한다.
- Textual presenter 관련 focused test를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.421`을 출력해야 한다.
