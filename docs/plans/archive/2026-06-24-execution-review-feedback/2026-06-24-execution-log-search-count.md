# Execution Log Search Count

## 문제

Full Log 모달은 검색/필터를 지원하지만, 검색 결과가 몇 줄인지 또는 500줄 window 때문에
일부 결과가 숨겨졌는지 알려주지 않는다.

사용자가 `failed`, `WP-001`, provider 이름으로 검색했을 때 결과 규모를 바로 알 수 있어야
긴 workflow log를 더 안정적으로 탐색할 수 있다.

## 설계

- 검색 입력 아래에 짧은 상태 라인을 추가한다.
- 검색어가 없으면 전체 log 기준으로 표시한다.
  - 예: `Showing 500 of 1200 lines`
- 검색어가 있으면 match 기준으로 표시한다.
  - 예: `Showing 12 of 12 matches`
  - 예: `0 matches`
- 한국어 UI에는 같은 정보를 한국어로 표시한다.
- 렌더링 window는 기존 `MAX_RENDERED_LOG_LINES`를 그대로 사용한다.
- log source, snapshot, export 동작은 변경하지 않는다.

## 테스트

- 검색어가 없을 때 전체 line count와 visible count가 표시된다.
- 검색어가 있을 때 match count가 표시된다.
- match가 없을 때 0 matches 문구가 표시된다.
- Input 변경 시 status line도 함께 갱신된다.
