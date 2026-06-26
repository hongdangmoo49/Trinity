# Execution Package Row Button Cache

## 배경

ExecutionPackageRow는 패키지 row projection이 바뀌면 텍스트 필드를 비교해 변경된 field만
`Static.update()`한다. 하지만 status나 executor처럼 텍스트만 바뀐 경우에도 detail/retry/review
버튼을 항상 조회하고 label/disabled 상태를 비교한다.

실행 페이지는 WP 상태가 자주 바뀌는 화면이므로 row 단위에서 불필요한 widget query를 줄이는
것이 누적 비용을 낮추는 데 도움이 된다.

## 개선 방향

- projection 적용 전 버튼 관련 상태를 snapshot으로 저장한다.
- detail button label/disabled 상태가 바뀐 경우에만 detail button을 조회한다.
- retry/review action label이 바뀐 경우에만 해당 버튼 목록을 조회한다.
- 텍스트 field 업데이트와 기존 row remount 정책은 유지한다.

## 범위

- `src/trinity/textual_app/screens/execution_matrix.py`
- `tests/test_execution_package_row.py`

## 검증

- status만 바뀌는 row update에서 button 조회가 발생하지 않는지 확인한다.
- detail button label이 바뀌면 기존처럼 button label이 갱신되는지 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
