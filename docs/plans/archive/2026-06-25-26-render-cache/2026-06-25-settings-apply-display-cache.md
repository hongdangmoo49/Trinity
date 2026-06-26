# Settings Apply Display Cache

## 배경

SettingsScreen은 사용자가 Apply를 누르면 UI 설정과 agent/central model 설정을 저장한 뒤
미리보기와 저장 상태 텍스트를 갱신한다. 저장 자체는 명시적인 사용자 액션이므로 유지해야
하지만, 표시 문자열이 동일한 경우에도 `Static.update()`가 반복 호출된다.

설정 화면은 실행 페이지처럼 고빈도 갱신 화면은 아니지만, 최근 Textual UI는 동일 표시값을
다시 그리지 않는 정책으로 정리되고 있다. SettingsScreen도 같은 정책을 적용하면 불필요한
위젯 mutation을 줄이고 화면 업데이트 흐름을 일관되게 유지할 수 있다.

## 개선 방향

- 최초 preview 문자열을 compose 시점에 render key로 저장한다.
- Apply 이후 preview 문자열이 기존 값과 같으면 `#theme-preview` 업데이트를 생략한다.
- 저장 상태 문자열이 기존 값과 같으면 `#settings-status` 업데이트를 생략한다.
- 설정 저장과 config 저장 동작은 변경하지 않는다.

## 범위

- `src/trinity/textual_app/screens/settings.py`
- `tests/test_textual_settings.py`

## 검증

- 같은 설정을 반복 적용할 때 preview/status update가 생략되는지 확인한다.
- 첫 저장 상태 표시처럼 문자열이 바뀌는 경우에는 기존처럼 update되는지 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
