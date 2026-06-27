# Provider Activity Frame Running Only

## Context

Nexus는 실행 중 표시를 위해 activity frame을 주기적으로 전진시킨다. 기존
ProviderPanel은 frame tick마다 모든 provider status widget을 갱신했다. 하지만
spinner prefix는 running 상태에서만 렌더링되므로 ready, waiting, issue, off 상태의
DOM update는 불필요하다.

## Scope

- ProviderPanel activity frame tick에서 running 상태만 status widget을 갱신한다.
- 비실행 상태도 내부 frame 값은 보관해 이후 running 전환 시 일관된 frame을 쓸 수
  있게 유지한다.
- running 상태의 spinner 갱신 동작은 유지한다.
- 패치 버전을 올린다.

## Acceptance Criteria

- Ready provider는 activity frame tick에서 status update를 호출하지 않는다.
- Running provider는 activity frame tick에서 status update를 호출한다.
- Nexus provider panel 기존 상태/라벨 테스트가 계속 통과한다.
