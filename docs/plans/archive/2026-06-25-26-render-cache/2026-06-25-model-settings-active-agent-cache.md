# Model Settings Active Agent Refresh Cache

## 배경

ModelSettingsModal은 `/model` 모달에서 agent별 model choices를 보여준다. 왼쪽 agent 버튼을 누르면 `active_agent`를 바꾸고 `_refresh_choices()`로 modal을 recompose한다.

현재는 이미 선택된 agent 버튼을 다시 눌러도 같은 `active_agent`를 다시 설정하고 전체 choices panel을 refresh한다. 화면 상태가 변하지 않는 클릭이므로 no-op 처리할 수 있다.

## 개선 방향

- `on_button_pressed()`에서 agent 버튼 클릭 시 next agent를 먼저 계산한다.
- next agent가 현재 `active_agent`와 같으면 event만 stop하고 바로 반환한다.
- 다른 agent로 전환하는 경우에는 기존처럼 `active_agent`를 갱신하고 `_refresh_choices()`를 호출한다.

## 범위

- `src/trinity/textual_app/widgets/model_settings_modal.py`
- `tests/test_model_settings_modal.py`

## 검증

- 현재 active agent 버튼을 다시 누를 때 `_refresh_choices()`가 호출되지 않는지 확인한다.
- 다른 agent 버튼을 누르면 기존처럼 `_refresh_choices()`가 호출되고 active agent가 바뀌는지 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
