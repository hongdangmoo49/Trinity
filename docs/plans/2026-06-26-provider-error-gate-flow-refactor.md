# Provider Error Gate Flow 분리

- 브랜치: `refactor/provider-error-gate-flow`
- 버전: `1.0.295` -> `1.0.296`
- 대상: `src/trinity/workflow/engine.py`, `src/trinity/workflow/provider_error_gate_flow.py`

## 배경

`WorkflowEngine`은 이미 실행 중단/재시도 경로를 `ExecutionRecoveryFlow`로 위임하고 있다. 반면 provider error gate는 pure helper인 `provider_error_gate.py`가 있음에도, 실제 session mutation, pending question 삽입, gate answer 처리, continue/stop/retry 결과 액션 생성은 여전히 `WorkflowEngine` 내부에 남아 있다.

이 때문에 `WorkflowEngine`이 deliberation 결과 적용, provider failure gate, 일반 질문 처리, 실행/review 흐름을 동시에 조율하게 되고, 이후 execution/review/post-review flow를 더 얇게 분리할 때 엔진의 책임 경계가 흐려진다.

## 개선안

1. `ProviderErrorGateFlow`를 추가해 provider error gate의 상태 변경 흐름을 담당하게 한다.
2. 기존 pure helper `provider_error_gate.py`는 gate 판정/plan/prompt/context 직렬화 역할로 유지한다.
3. `WorkflowEngine`은 flow 생성, gate 질문 여부 확인, gate open/answer 위임만 수행한다.
4. 기존 provider error gate 테스트를 유지하고, flow 단위 테스트를 추가해 continue 불가/stop/retry 액션을 직접 검증한다.

## 범위

- 동작 변경 없음
- 새 사용자 UI 없음
- provider retry prompt/context 포맷 변경 없음
- execution recovery flow 변경 없음

## 기대 효과

- `WorkflowEngine`의 provider error gate 책임을 얇은 facade 호출로 줄인다.
- session mutation과 gate answer routing을 한 클래스로 모아 후속 recovery/review flow 분리와 충돌을 줄인다.
- 기존 테스트를 유지하면서 flow 단위 회귀 테스트로 책임 경계를 명확히 한다.
