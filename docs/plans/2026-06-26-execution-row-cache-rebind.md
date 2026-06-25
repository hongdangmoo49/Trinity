# ExecutionPackageRow 캐시 재바인딩 보강

- 브랜치: `perf/execution-row-cache-rebind`
- 버전: `1.0.285` -> `1.0.286`
- 대상: `src/trinity/textual_app/screens/execution_matrix.py`

## 배경

실행 페이지의 `ExecutionPackageRow`는 WP 행의 정적 필드와 버튼을 캐시해 상태 갱신 시 반복 `query_one()`을 피한다. 하지만 compose 시작 시 캐시를 명시적으로 초기화하지 않아, 행 위젯이 `refresh(recompose=True)`로 다시 그려지면 이전 compose의 위젯 참조가 남을 수 있다.

행 위젯은 현재 화면 갱신 경로에서 대체로 remount되지만, Textual 리컴포즈가 발생했을 때도 cache 정책이 일관되어야 한다. stale 참조가 남으면 이후 `update_projection()`이 새로 그려진 행이 아니라 이전 위젯을 갱신할 수 있다.

## 개선안

1. `ExecutionPackageRow.compose()` 시작 시 `_static_cache`와 `_button_cache`를 초기화한다.
2. compose 중 새로 생성한 `Static`/`Button` 위젯을 다시 캐시에 저장한다.
3. 리컴포즈 뒤 캐시가 새 위젯을 가리키고, `update_projection()`이 DOM 재조회 없이 새 위젯을 갱신하는지 테스트한다.

## 기대 효과

- 실행 매트릭스 행 리컴포즈 이후 stale 위젯 참조를 방지한다.
- WP 상태/버튼 갱신의 캐시 정책을 다른 Nexus 위젯과 맞춘다.
- 향후 행 단위 refresh/recompose 최적화를 적용할 때 안정적인 기반을 제공한다.
