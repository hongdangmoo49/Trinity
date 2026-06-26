# Waiting Status Bucket Polish

## Context

한국어 상세 화면에서는 `needs_user_decision`과 `waiting_for_external_input`이
사용자 결정 대기, 외부 입력 대기처럼 읽히지만, compact 상태 버킷은 이 값을
대기 상태로 분류하지 않으면 Nexus 실행 목록이나 provider panel에서 `?`로 보일
수 있다.

## Scope

- `needs_user_decision`을 waiting compact bucket으로 분류한다.
- `waiting_for_external_input`을 waiting compact bucket으로 분류한다.
- provider panel과 execution matrix가 같은 공용 상태 분류를 쓰도록 회귀 테스트를
  보강한다.
- 패치 버전을 올린다.

## Acceptance Criteria

- English compact UI에서 두 상태가 `WAIT`로 표시된다.
- Korean compact UI에서 두 상태가 `대기`로 표시된다.
- 상세 상태값 번역과 알 수 없는 커스텀 상태값 fallback은 기존 동작을 유지한다.
