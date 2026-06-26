# Model Settings Choice Refresh Cache

## 배경

ModelSettingsModal은 provider model discovery 결과를 받을 때 `set_model_choices()`에서 choices를 dict에 update하고, 모달이 mount되어 있으면 항상 `refresh(recompose=True)`를 호출한다. 같은 choices가 다시 들어오는 경우에도 전체 모달 recompose가 발생한다.

모델 discovery 결과는 Start/Nexus 화면에서 반복 전달될 수 있으므로, 선택지 데이터가 실제로 바뀐 경우에만 모달을 다시 그리는 편이 낫다.

## 개선 방향

- `set_model_choices()`에서 agent별 기존 choices와 새 choices를 tuple로 비교한다.
- 하나라도 바뀐 경우에만 내부 choices를 갱신하고 `_refresh_choices()`를 호출한다.
- 같은 choices 재전달은 no-op으로 처리한다.

## 범위

- `src/trinity/textual_app/widgets/model_settings_modal.py`
- `tests/test_model_settings_modal.py`

## 검증

- 같은 choices를 다시 적용할 때 refresh가 생략되는지 확인한다.
- choices가 바뀌면 refresh가 호출되고 내부 choices가 갱신되는지 확인한다.
- ModelSettingsModal focused test와 전체 테스트를 통과시킨다.
