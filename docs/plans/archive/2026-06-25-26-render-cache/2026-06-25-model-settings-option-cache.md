# Model Settings Option Selection Cache

## 배경

ModelSettingsModal의 model option list는 option 선택 시 `selected_models`를 갱신하고 `_refresh_choices()`로 modal을 recompose한다. 현재 선택된 model option을 다시 선택해도 같은 model 값을 다시 저장하고 refresh가 발생한다.

이미 선택된 option 재선택은 UI 상태가 변하지 않는 입력이므로 no-op 처리할 수 있다. 특히 `/model` 모달에서 키보드/마우스 입력이 반복될 때 불필요한 recompose를 줄인다.

## 개선 방향

- option 선택 이벤트에서 선택된 choice model을 계산한다.
- 현재 active agent의 selected model과 같으면 event만 stop하고 바로 반환한다.
- 다른 model을 선택하는 경우에는 기존처럼 `selected_models`를 갱신하고 `_refresh_choices()`를 호출한다.

## 범위

- `src/trinity/textual_app/widgets/model_settings_modal.py`
- `tests/test_model_settings_modal.py`

## 검증

- 현재 선택된 option을 다시 선택할 때 `_refresh_choices()`가 호출되지 않는지 확인한다.
- 다른 option을 선택하면 selected model이 바뀌고 `_refresh_choices()`가 호출되는지 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
