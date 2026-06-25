# Execution Log Modal Window Optimization

## Context

Full Execution Log modal은 기본 상태에서 검색어가 없어도 `_filtered_lines("")`를
통해 전체 로그를 복사한다. `_refresh_log()`는 상태 문구와 렌더링을 각각 계산하므로
큰 로그에서는 같은 전체 복사가 반복될 수 있다.

## Scope

- 검색어가 없는 기본 렌더링 경로에서 전체 로그 복사를 제거한다.
- 기본 상태 문구는 `len(self.lines)`만 사용한다.
- 기본 렌더링은 마지막 `MAX_RENDERED_LOG_LINES` window만 인덱스로 읽는다.
- 검색 경로는 기존처럼 전체 scan/filter 동작을 유지한다.
- 패치 버전을 올린다.

## Acceptance Criteria

- 큰 로그를 검색어 없이 열 때 전체 로그를 iterate하지 않는다.
- hidden count와 마지막 window 표시는 기존과 동일하다.
- 검색 필터링과 검색 결과 count 동작은 기존과 동일하다.
