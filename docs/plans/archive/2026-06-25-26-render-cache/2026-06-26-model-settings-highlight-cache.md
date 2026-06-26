# Model Settings Highlight Cache

## 배경

ModelSettingsModal은 active agent의 선택된 모델을 `OptionList.highlighted`에 동기화한다.
선택지 refresh나 모달 mount 이후 같은 active agent, 같은 selected model, 같은 choice 목록에서
`_sync_choice_highlight()`가 반복 호출되면 `#model-choice-list` 조회와 highlighted 대입이 다시
발생한다.

모델 설정 모달은 리컴포즈를 통해 choice list를 새로 만들 수 있으므로 캐시가 새 위젯의 초기
highlight 적용을 막으면 안 된다. 따라서 refresh/recompose 경로에서는 캐시를 무효화하고,
동일 위젯 상태에서 같은 highlight 동기화만 생략하는 방식이 안전하다.

## 개선 방향

- active agent, selected model, choice model tuple, target index로 highlight render key를 만든다.
- render key가 같으면 `_sync_choice_highlight()`에서 바로 반환한다.
- `_refresh_choices()`가 리컴포즈를 예약할 때 highlight key를 무효화한다.
- 선택된 모델이 없는 경우에도 기존처럼 0번 항목을 highlight한다.

## 범위

- `src/trinity/textual_app/widgets/model_settings_modal.py`
- `tests/test_model_settings_modal.py`

## 검증

- 같은 highlight state를 다시 동기화할 때 `#model-choice-list` 조회가 생략되는지 확인한다.
- selected model이 바뀌면 기존처럼 choice list를 조회하고 highlighted index가 갱신되는지 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
