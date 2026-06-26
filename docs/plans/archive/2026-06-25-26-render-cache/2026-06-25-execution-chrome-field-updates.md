# Execution Chrome Field-Level Updates

## 배경

실행 페이지 chrome은 header, summary, task toggle, activity toggle, retry button 상태를 하나의 render key로 캐시한다. render key가 완전히 같으면 갱신을 생략하지만, 일부 field만 바뀌어도 모든 chrome 위젯을 다시 update/label 대입했다.

WP 실행 중에는 summary나 retry 가능 여부처럼 일부 chrome field만 변할 수 있으므로, 변경된 field만 갱신하면 반복 렌더 비용을 더 줄일 수 있다.

## 개선 방향

- 마지막 `_ChromeProjection`을 저장한다.
- render key가 바뀐 경우에도 이전 projection과 비교해 변경된 field만 갱신한다.
- 전체 render key가 같은 경우에는 기존처럼 즉시 반환한다.

## 범위

- `src/trinity/textual_app/screens/execution_matrix.py`
- `tests/test_execution_chrome.py`

## 검증

- summary만 바뀌는 chrome projection 적용 시 summary만 update되는지 확인한다.
- 실행 페이지 관련 focused test와 전체 테스트를 통과시킨다.
