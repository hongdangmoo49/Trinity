# ModelSettingsModal 선택 목록 캐시 보강

- 브랜치: `perf/model-settings-choice-list-cache`
- 버전: `1.0.282` -> `1.0.283`
- 대상: `src/trinity/textual_app/widgets/model_settings_modal.py`

## 배경

Nexus 실행 페이지의 모달/패널 위젯은 상태 갱신 중 `query_one()` 반복 호출을 줄이는 방향으로 보강하고 있다. `ModelSettingsModal`은 에이전트별 모델 선택 목록을 다시 그린 뒤 현재 선택 모델의 highlight를 맞추는데, 이 과정에서 `#model-choice-list`를 직접 조회한다.

선택 목록은 모달 안에 하나만 존재하며 compose 시점에 생성되므로, 위젯 참조를 캐시하면 highlight 동기화 시 반복 조회를 피할 수 있다. 다만 에이전트 전환이나 모델 후보 갱신으로 `refresh(recompose=True)`가 호출될 때는 기존 `OptionList`가 교체되므로 stale 참조를 방지해야 한다.

## 개선안

1. `ModelSettingsModal`에 `_choice_list_widget` 캐시를 추가한다.
2. `compose()` 시작 시 캐시를 초기화한다.
3. 새 `OptionList`를 생성하는 즉시 캐시에 저장한다.
4. highlight 동기화는 `_choice_list()` 헬퍼를 통해 캐시를 사용하고, 캐시가 비어 있을 때만 DOM 조회로 복구한다.
5. 테스트는 다음을 확인한다.
   - 선택 상태가 바뀌어도 highlight 동기화가 `query_one("#model-choice-list")`를 반복하지 않는다.
   - 에이전트 전환으로 리컴포즈된 뒤 캐시가 새 `OptionList`를 가리킨다.

## 기대 효과

- 모델 설정 모달에서 상태 동기화 비용을 줄인다.
- 리컴포즈 이후 stale 위젯 참조로 인한 highlight 불일치 가능성을 줄인다.
- 실행 페이지 위젯 캐시 정책을 다른 모달과 같은 방식으로 맞춘다.
