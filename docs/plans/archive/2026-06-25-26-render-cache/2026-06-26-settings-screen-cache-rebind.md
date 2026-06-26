# SettingsScreen 캐시 재바인딩 보강

- 브랜치: `perf/settings-screen-cache-rebind`
- 버전: `1.0.283` -> `1.0.284`
- 대상: `src/trinity/textual_app/screens/settings.py`

## 배경

Textual 화면과 모달의 고정 위젯 조회는 compose 시점에 캐시하고, 상태 갱신 시 반복 `query_one()`을 피하는 방향으로 정리하고 있다. `SettingsScreen`도 select/preview/status 위젯을 캐시하지만, 화면이 `refresh(recompose=True)`로 다시 그려질 때 기존 캐시를 명시적으로 초기화하지 않는다.

특히 status 영역은 새로 compose되면 빈 `Static`으로 돌아가는데 `_status_key`가 이전 `"Saved"` 상태로 남을 수 있다. 이 경우 이후 저장을 눌러도 같은 문자열로 판단해 status 표시 갱신을 건너뛸 수 있다.

## 개선안

1. `compose()` 시작 시 select 캐시와 preview/status 위젯 참조를 초기화한다.
2. 새 status 위젯은 빈 문자열로 시작하므로 `_status_key`도 함께 초기화한다.
3. recompose 이후 `action_apply()`가 DOM 재조회 없이 새 캐시만 사용하고 status를 다시 표시하는지 테스트한다.

## 기대 효과

- 설정 화면 recompose 이후 stale 위젯 참조를 방지한다.
- status 표시 상태와 실제 새 위젯 내용이 어긋나는 문제를 줄인다.
- Nexus/실행 페이지에서 적용한 compose-time cache 정책과 설정 화면의 동작을 맞춘다.
