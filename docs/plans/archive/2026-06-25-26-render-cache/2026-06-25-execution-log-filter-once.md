# Execution Log Search Filter Once

## Context

Full Execution Log modal은 검색어가 변경될 때 상태 문구와 렌더링 라인을 각각
계산한다. 기존 구조에서는 `_status_text(query)`와 `_render_lines(query)`가 모두
`_filtered_lines(query)`를 호출해 같은 로그 검색을 두 번 수행한다.

## Scope

- 모달 refresh 경로에서 상태 문구와 렌더링 라인을 한 번에 계산한다.
- 검색어가 있는 경우 `_filtered_lines(query)`를 한 번만 호출한다.
- 기존 `_render_lines()`와 `_status_text()` helper 동작은 유지한다.
- 검색어가 없는 window 기반 최적화 동작은 유지한다.
- 패치 버전을 올린다.

## Acceptance Criteria

- `_render_state("FAILED")`는 필터링을 한 번만 수행한다.
- 검색 결과 상태 문구와 렌더링 라인은 기존과 동일하다.
- 기존 full log modal 검색 테스트가 계속 통과한다.
