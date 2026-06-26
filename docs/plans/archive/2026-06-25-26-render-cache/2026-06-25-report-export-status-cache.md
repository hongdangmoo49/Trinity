# Report Export Status Cache

## 배경

ReportScreen은 Markdown export가 끝난 뒤 `show_export_path()`로 저장 경로를 header status에 표시한다. 같은 export path가 반복 전달되면 화면에 표시될 status 문자열은 변하지 않지만 `Static.update()`가 매번 호출된다.

본문 렌더링에는 snapshot/report identity cache가 들어가 있으므로, header status도 같은 문자열 재적용을 생략하면 report 화면의 작은 반복 update를 줄일 수 있다.

## 개선 방향

- ReportScreen이 마지막으로 표시한 export status 문자열을 저장한다.
- `show_export_path()`에서 다음 status 문자열이 기존 값과 같으면 바로 반환한다.
- path나 locale label이 달라져 status 문자열이 바뀌는 경우에는 기존처럼 `Static.update()`를 호출한다.

## 범위

- `src/trinity/textual_app/screens/report.py`
- `tests/test_report_screen_identity_cache.py`

## 검증

- 같은 export path가 반복 전달될 때 status update가 생략되는지 확인한다.
- 다른 export path가 전달되면 status update가 발생하는지 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
