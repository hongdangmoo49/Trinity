# Textual Target Cancel Presenter

## 목적

workspace/target 선택 흐름에서 반복되는 control repo 확인 취소 메시지 생성을 pure presenter 함수로 분리한다.

## 범위

- target 선택 취소와 실행 preflight 취소 결과를 `LocalCommandSnapshot`으로 만드는 presenter 함수를 추가한다.
- Nexus workspace 선택, `/target` 확인, execution preflight 확인 취소 흐름이 같은 presenter 경로를 사용하게 정리한다.
- 기존 warning severity, empty 상태, action hint, 한글/영문 문구는 유지한다.
- 패치 버전을 `1.0.430`으로 올린다.

## 비목표

- control repo 확인 modal 표시 조건은 변경하지 않는다.
- target workspace 설정/생성 정책은 변경하지 않는다.
- workspace picker UI는 변경하지 않는다.

## 검증

- target cancel presenter focused test를 보강한다.
- 관련 Textual app target cancel focused test를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.430`을 출력해야 한다.
