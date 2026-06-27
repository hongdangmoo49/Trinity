# Textual Report Route Preparer

## 목적

`switch_to("report")`에 남아 있는 snapshot fallback 적용과 structured report 생성 로직을 helper로 분리해 `TrinityTextualApp`의 route 전환 책임을 줄인다.

## 범위

- report screen에 snapshot fallback을 적용한 뒤, 저장된 workflow session이 있으면 structured `DeliberationReport`를 생성해 적용하는 helper를 추가한다.
- structured report 생성 중 예외가 발생해도 기존처럼 snapshot fallback 렌더링을 유지한다.
- `switch_to("report")`는 report screen 조회, snapshot 선택, helper 호출만 담당한다.
- 패치 버전을 `1.0.426`으로 올린다.

## 비목표

- report 화면의 렌더링 마크업이나 export 동작은 변경하지 않는다.
- workflow persistence 파일 형식과 event loading 정책은 변경하지 않는다.
- report route 외의 route 전환 로직은 변경하지 않는다.

## 검증

- report route helper focused test를 추가한다.
- report route 관련 Textual app focused test를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.426`을 출력해야 한다.
