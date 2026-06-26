# ExecutionMatrixScreen 렌더 키 재바인딩 보강

- 브랜치: `perf/execution-screen-render-key-rebind`
- 버전: `1.0.287` -> `1.0.288`
- 대상: `src/trinity/textual_app/screens/execution_matrix.py`

## 배경

`ExecutionMatrixScreen`은 header/summary/package list/log 같은 고정 위젯을 compose 시점에 캐시하고, 상태 갱신 때는 render key와 snapshot identity를 사용해 불필요한 재렌더를 건너뛴다. 하지만 화면이 `refresh(recompose=True)`로 다시 그려지면 DOM은 새 위젯으로 교체되고 package list/log는 비어 있는 상태로 시작한다.

기존 compose 경로는 위젯 참조만 초기화하고 `_applied_state_identity`, `_chrome_render_key`, `_package_list_identity`, `_activity_lines_key` 같은 렌더 결정 키는 유지할 수 있었다. 그러면 같은 snapshot을 다시 적용했을 때 새 화면이 비어 있어도 이미 반영된 상태로 판단해 렌더를 건너뛸 수 있다.

## 개선안

1. compose 시작 시 고정 위젯 캐시와 함께 렌더 키 캐시도 초기화한다.
2. package row identity/cache, chrome projection key, activity log key, applied state identity, task expanded class key를 새 DOM 기준으로 리셋한다.
3. 리컴포즈 후 같은 snapshot 객체를 다시 적용해도 DOM 재조회 없이 새 header/summary/package/log가 렌더되는지 테스트한다.

## 기대 효과

- 실행 페이지 리컴포즈 후 stale render key로 인한 빈 화면/오래된 상태를 방지한다.
- WP package list와 activity log가 새 DOM에 확실히 재렌더된다.
- 실행 페이지의 widget cache와 render cache 생명주기를 같은 compose 경계로 맞춘다.
