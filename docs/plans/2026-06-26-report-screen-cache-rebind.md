# ReportScreen 캐시 재바인딩 보강

- 브랜치: `perf/report-screen-cache-rebind`
- 버전: `1.0.286` -> `1.0.287`
- 대상: `src/trinity/textual_app/screens/report.py`

## 배경

`ReportScreen`은 export status와 body 컨테이너를 compose 시점에 캐시하고, 같은 snapshot/report 객체 또는 같은 렌더 결과는 다시 그리지 않도록 identity/render key를 사용한다. 하지만 화면이 `refresh(recompose=True)`로 다시 그려지면 실제 DOM은 새 위젯으로 교체되는데, `_export_status_key`, `_last_rendered_id`, `_applied_source_identity`가 이전 값을 유지할 수 있다.

이 상태에서는 새 status 위젯이 비어 있어도 같은 export path 업데이트를 건너뛰거나, 새 body가 placeholder 상태인데 같은 snapshot/report 입력을 이미 렌더된 것으로 판단할 수 있다.

## 개선안

1. `compose()` 시작 시 export status/body 위젯 캐시를 초기화한다.
2. 새 status 위젯은 빈 문자열로 시작하므로 `_export_status_key`도 초기화한다.
3. 새 body는 placeholder 상태로 시작하므로 `_last_rendered_id`와 `_applied_source_identity`도 초기화한다.
4. 리컴포즈 후 같은 export path와 같은 snapshot 객체를 다시 적용해도 DOM 재조회 없이 새 위젯에 렌더되는지 테스트한다.

## 기대 효과

- 리포트 화면 recompose 이후 stale 위젯 참조를 방지한다.
- 같은 데이터 재적용이 새 DOM에 반영되지 않는 상태 불일치를 줄인다.
- Nexus 실행/리포트 화면의 compose-time cache 정책을 일관되게 유지한다.
