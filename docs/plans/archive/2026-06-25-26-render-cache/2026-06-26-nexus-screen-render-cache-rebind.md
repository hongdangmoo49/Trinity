# NexusScreen 렌더 캐시 재바인딩 보강

- 브랜치: `perf/nexus-screen-render-cache-rebind`
- 버전: `1.0.294` -> `1.0.295`
- 대상: `src/trinity/textual_app/screens/nexus.py`

## 배경

`NexusScreen`은 provider panel, 중앙 에이전트, 질문 패널, 워크플로우 인스펙터, 대상 workspace label, composer를 조합하는 최상위 실행 화면이다. 반복 snapshot 적용 비용을 줄이기 위해 `_applied_snapshot_identity`로 같은 snapshot 객체 재적용을 건너뛰고, `_provider_state_cache`로 provider panel의 동일 상태 업데이트를 생략한다.

하지만 `refresh(recompose=True)` 이후에는 provider panel과 중앙/질문/인스펙터 위젯이 새로 만들어진다. 기존 compose 경로는 위젯 참조만 초기화했기 때문에, 같은 snapshot 객체가 다시 적용되면 전체 적용이 스킵되거나, identity를 비워도 provider state cache가 남아 새 provider panel 업데이트가 생략될 수 있다.

## 개선안

1. compose 시작 시 고정 위젯 캐시와 함께 snapshot/provider render cache를 초기화한다.
2. `_provider_state_cache`, `_applied_snapshot_identity`, `_workspace_label_key`를 새 DOM 기준으로 리셋한다.
3. compose에서 workspace label Static을 만든 직후 현재 label key를 다시 묶는다.
4. 리컴포즈 후 같은 snapshot 객체를 다시 적용해 provider summary와 중앙 패널 snapshot이 복구되는지 테스트한다.

## 기대 효과

- Nexus 화면 재구성 후 provider panel, 중앙 패널, 질문/인스펙터 갱신이 빈 상태로 남는 문제를 방지한다.
- 기존 같은 snapshot/provider 상태 스킵 최적화는 유지하면서 새 DOM 생명주기와 캐시 수명주기를 맞춘다.
- 실행 페이지 최상위 화면과 하위 위젯들의 render cache 정책을 일관되게 맞춘다.
