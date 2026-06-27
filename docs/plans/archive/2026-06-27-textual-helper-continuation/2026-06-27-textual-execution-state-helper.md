# Textual Execution State Helper

## 목적

`TrinityTextualApp`에 남아 있는 `ExecutionMatrixScreen.apply_execution_state()` 직접 호출을 내부 helper로 모아 실행 화면 반영 책임을 한곳으로 좁힌다.

## 범위

- 앱 내부 helper `_apply_execution_screen_state()`를 추가한다.
- review repair retry, workspace preflight 실행 시작, workflow outcome 갱신, execute retry 선택 흐름의 직접 호출을 helper 호출로 바꾼다.
- 기존 `switch_to("execution")` 시점, preflight 선택, snapshot 적용 대상은 유지한다.
- 패치 버전을 `1.0.435`로 올린다.

## 비목표

- `ExecutionMatrixScreen`의 렌더링, 상태 모델, modal 동작은 변경하지 않는다.
- `apply_current_route_snapshot()`의 route 전환 동작은 변경하지 않는다.
- 실행 retry/recovery 정책은 변경하지 않는다.

## 검증

- 실행/재시도/리뷰 보정 관련 Textual app focused test를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.435`를 출력해야 한다.
