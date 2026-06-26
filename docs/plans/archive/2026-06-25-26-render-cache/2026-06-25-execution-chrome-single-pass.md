# Execution Chrome Single Pass Summary

## Context

Execution Matrix chrome 영역은 summary text, retry label, retry disabled 상태를
계산하면서 work package 목록을 여러 번 순회할 수 있다. package list와 log update는
이미 변경 감지를 적용했지만, chrome projection 자체가 polling마다 불필요하게 여러
번 계산되면 큰 실행 계획에서 비용이 누적된다.

## Scope

- header/summary/button 상태를 `_ChromeProjection`으로 묶는다.
- summary counts, retry count, parallel lane count, serial count를 한 번의 package
  pass에서 계산한다.
- 기존 `_summary_text()`, `_retry_button_label()`, `_parallel_summary_parts()`
  helper의 외부 동작은 유지한다.
- 패치 버전을 올린다.

## Acceptance Criteria

- chrome projection 계산은 work package 목록을 한 번만 순회한다.
- summary text, retry button label/disabled, lane/serial 표시가 기존과 동일하다.
- 기존 execution matrix focused tests와 전체 테스트가 통과한다.
