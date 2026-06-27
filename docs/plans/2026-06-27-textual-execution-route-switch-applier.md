# Textual Execution Route Switch Applier

## 목적

`switch_to("execution")`에 남아 있는 Execution Matrix snapshot 적용 중복을 route snapshot helper로 통합한다.

## 범위

- route snapshot helper가 execution route에서 preflight 없이도 적용할 수 있는 옵션을 제공한다.
- `_refresh_current_route_from_active_snapshot()`은 기존처럼 preflight가 있을 때만 execution route를 갱신한다.
- `switch_to("execution")`은 기존 동작처럼 preflight가 없어도 Execution Matrix에 snapshot을 먼저 적용한다.
- 패치 버전을 `1.0.425`로 올린다.

## 비목표

- report route의 structured report 생성 로직은 변경하지 않는다.
- execution screen의 렌더링 정책이나 preflight 모델은 변경하지 않는다.

## 검증

- route snapshot helper focused test를 보강한다.
- execution route switch 관련 Textual app focused test를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.425`를 출력해야 한다.
