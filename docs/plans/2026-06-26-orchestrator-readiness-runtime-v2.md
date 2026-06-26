# Orchestrator Readiness Runtime 추가 분리

- 브랜치: `refactor/orchestrator-readiness-runtime-v2`
- 버전: `1.0.296` -> `1.0.297`
- 대상: `src/trinity/orchestrator.py`, `src/trinity/orchestrator_readiness.py`

## 배경

`OrchestratorReadinessRuntime`은 provider readiness 판정과 one-shot preflight 판정을 이미 담당한다. 그러나 `TrinityOrchestrator`에는 판정 결과를 내부 상태에 적용하고, degraded mode에서 ready agent만 남기도록 여러 런타임 구성요소를 재바인딩하는 세부 로직이 남아 있다.

이 구조에서는 `TrinityOrchestrator`가 readiness 판정, readiness 상태 저장, degraded agent 재구성, status projection을 함께 알고 있어 후속 execution/review/post-review flow 분리 시 책임 경계가 다시 흐려질 수 있다.

## 개선안

1. readiness outcome 적용을 담당하는 runtime-side binder를 추가한다.
2. `TrinityOrchestrator`는 binder 생성과 공개 상태 조회만 수행하도록 축소한다.
3. readiness failure 포맷/이벤트 emit/one-shot status helper의 단순 위임 메서드를 제거한다.
4. degraded mode에서 agent set을 줄일 때 protocol, execution, review, monitor, rotator, health checker 재바인딩이 유지되는지 단위 테스트로 고정한다.

## 범위

- provider readiness 정책 변경 없음
- strict/degraded 동작 변경 없음
- TUI event payload 변경 없음
- public CLI/API 동작 변경 없음

## 기대 효과

- `TrinityOrchestrator`의 readiness 책임을 facade 호출로 줄인다.
- readiness 상태 적용과 degraded runtime 재바인딩을 한 모듈에 모아 회귀 테스트가 쉬워진다.
- 이후 execution/review/post-review flow를 분리할 때 orchestrator의 상태 조립 책임이 더 작아진다.
