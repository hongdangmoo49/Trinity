# Textual Execution Recovery Presenter

## 목적

`TrinityTextualApp`에 남아 있는 execution recovery local command 표시 데이터 생성을 pure presenter 함수로 분리한다.

## 범위

- execution recovery 결과를 `LocalCommandSnapshot`으로 만드는 presenter 함수를 추가한다.
- workflow outcome message 지역화, recovery markdown, action hint, table rows/columns 조립을 presenter로 옮긴다.
- `TrinityTextualApp`은 생성된 결과를 기록하고 화면에 반영하는 역할만 유지한다.
- 기존 `/execute-retry`, `/execute mark-interrupted`, `/execute abort` 동작은 변경하지 않는다.
- 패치 버전을 `1.0.422`로 올린다.

## 비목표

- execution recovery 상태 모델이나 retry 정책은 변경하지 않는다.
- Nexus/Execution Matrix 화면 배치는 변경하지 않는다.

## 검증

- execution recovery presenter focused test를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.422`를 출력해야 한다.
