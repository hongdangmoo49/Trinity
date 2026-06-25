# Execution Log Recent Slice Optimization

## Context

Execution Matrix의 최근 로그 영역은 화면에 마지막 7줄만 표시한다. 하지만 기존
구현은 refresh마다 `list(snapshot.execution_log)`로 전체 로그를 복사한 뒤 마지막
7줄을 잘라 렌더링한다. 실행 로그가 길어질수록 Nexus/Execution 화면 갱신 비용이
불필요하게 증가할 수 있다.

## Scope

- 최근 로그 표시 경로에서 전체 execution log 복사를 제거한다.
- 화면에는 기존처럼 activity header, 숨김 줄 수, 최근 7줄만 표시한다.
- 전체 로그 모달을 열 때는 기존처럼 전체 로그를 리스트로 넘긴다.
- workflow event fallback 동작은 유지한다.
- 패치 버전을 올린다.

## Acceptance Criteria

- 최근 로그 표시가 긴 로그 전체를 iterate하지 않고 마지막 window만 읽는다.
- 최근 로그 UI의 hidden count와 표시 줄 수는 기존과 동일하다.
- full log modal은 계속 전체 로그를 받을 수 있다.
