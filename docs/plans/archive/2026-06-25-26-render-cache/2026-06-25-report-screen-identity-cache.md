# Report Screen Identity Apply Cache

## 배경

ReportScreen은 `apply_snapshot()`과 `apply_report()` 입력을 받아 리포트 본문을 다시 그린다. 내부 `_render_report()`에는 `repr(...)` 기반 render id cache가 있어 동일 내용의 재렌더는 막지만, 같은 snapshot/report 객체가 반복 적용되는 경우에도 큰 객체의 `repr` 해시 계산 비용은 계속 발생한다.

Nexus와 Execution 화면은 이미 같은 객체 재적용을 상위 화면에서 생략하도록 보강되어 있다. Report 화면도 같은 정책을 적용하면 route refresh와 report 화면 재진입 시 불필요한 작업을 줄일 수 있다.

## 개선 방향

- ReportScreen이 마지막으로 적용한 입력 source와 객체 id를 저장한다.
- mounted 상태에서 같은 `snapshot` 객체가 `apply_snapshot()`으로 다시 들어오면 `self.snapshot`만 유지하고 바로 반환한다.
- mounted 상태에서 같은 structured `report` 객체가 `apply_report()`로 다시 들어오면 `self._report`만 유지하고 바로 반환한다.
- snapshot fallback과 structured report 경로가 서로 덮어쓰는 흐름은 유지하기 위해 cache key에 source 타입을 포함한다.
- 같은 내용의 새 객체는 기존 render id 비교 경로를 그대로 통과한다.

## 범위

- `src/trinity/textual_app/screens/report.py`
- `tests/test_report_screen_identity_cache.py`

## 검증

- 같은 snapshot 객체를 다시 적용할 때 `_render_report()`가 호출되지 않는지 확인한다.
- 같은 내용의 새 snapshot 객체는 기존처럼 `_render_report()` 경로를 통과하는지 확인한다.
- 같은 structured report 객체를 다시 적용할 때 `_render_report()`가 호출되지 않는지 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
