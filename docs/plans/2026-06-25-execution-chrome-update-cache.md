# Execution Chrome Update Cache

## Context

Execution Matrix는 package list와 recent log에는 변경 감지를 적용한다. 하지만
header, summary, toolbar button label/disabled 상태는 같은 snapshot이 다시
적용되어도 매번 Textual widget update를 수행한다. 실행 중 snapshot polling이 잦으면
작은 update도 누적되어 화면 갱신 비용을 키울 수 있다.

## Scope

- execution header/summary/button 상태를 하나의 render key로 계산한다.
- render key가 이전과 같으면 chrome 영역 widget update를 생략한다.
- package list와 log의 기존 변경 감지 동작은 유지한다.
- 패치 버전을 올린다.

## Acceptance Criteria

- 같은 snapshot을 반복 적용하면 header/summary update가 다시 호출되지 않는다.
- summary, retry button 상태, task toggle label이 바뀌면 기존처럼 chrome 영역이
  갱신된다.
- 기존 execution matrix 테스트가 계속 통과한다.
