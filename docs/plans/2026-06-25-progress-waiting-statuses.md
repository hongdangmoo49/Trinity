# Progress Summary Waiting Status Polish

## Context

Nexus provider panel과 execution matrix는 `needs_user_decision`,
`waiting_for_external_input`을 대기 상태로 표시한다. 반면 Inspector의 progress
summary는 별도 상태 집계를 사용해 같은 상태를 `unknown`으로 계산할 수 있다.

## Scope

- progress summary의 waiting 상태 집합에 사용자 결정 대기, 외부 입력 대기,
  결정 대기 상태를 추가한다.
- current/next/blocked helper와 progress bar가 보강된 waiting 분류를 사용하도록
  회귀 테스트를 업데이트한다.
- 패치 버전을 올린다.

## Acceptance Criteria

- progress summary count에서 `needs_user_decision`과
  `waiting_for_external_input`은 waiting으로 집계된다.
- next work package 목록이 해당 대기 상태를 실행 후보로 노출한다.
- blocked/result 상태 우선순위는 기존처럼 waiting보다 우선한다.
