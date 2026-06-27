# Textual Review Repair Presenter

## 목적

`TrinityTextualApp`에 남아 있는 review repair local command 표시 데이터 생성을 pure presenter 함수로 분리한다.

## 범위

- review repair 결과를 `LocalCommandSnapshot`으로 만드는 presenter 함수를 추가한다.
- title, markdown body, action hint, table rows/columns 조립을 presenter로 옮긴다.
- `TrinityTextualApp`은 생성된 local command snapshot을 기록하고 화면에 반영하는 역할만 유지한다.
- 기존 `/review` repair 안내 동작은 변경하지 않는다.
- 패치 버전을 `1.0.423`으로 올린다.

## 비목표

- review repair 상태 모델이나 retry/accept/stop 정책은 변경하지 않는다.
- 중앙 패널 UI 배치는 변경하지 않는다.

## 검증

- review repair presenter focused test를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.423`을 출력해야 한다.
