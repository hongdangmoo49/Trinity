# Composer Inactive Palette Refresh Cache

## 배경

PromptComposer는 TextArea 변경마다 slash command palette 상태를 갱신한다. slash query가 없는 일반 텍스트 입력에서는 command matches를 비우고 option render, palette hide 경로를 반복한다.

이미 slash query가 없고 palette도 숨겨진 상태라면 화면 상태가 변하지 않는다. 이 경우 `_render_command_options()`와 `_set_command_palette_visible(False)` 호출을 생략해 일반 입력 중 불필요한 palette 갱신 비용을 줄일 수 있다.

## 개선 방향

- `_refresh_command_palette()`에서 query가 `None`인 경우 현재 palette 상태가 이미 inactive인지 확인한다.
- 이전 slash query가 없고, command matches/window/selection이 초기 상태이며, palette visible key가 `False`이면 바로 반환한다.
- slash palette가 열린 상태에서 일반 텍스트로 바뀌는 경우에는 기존처럼 options를 비우고 palette를 숨긴다.

## 범위

- `src/trinity/textual_app/widgets/composer.py`
- `tests/test_prompt_composer_palette_cache.py`

## 검증

- slash query가 없는 상태에서 반복 refresh될 때 option render와 palette visibility 적용이 생략되는지 확인한다.
- slash query가 있던 상태에서 일반 텍스트로 바뀌면 기존처럼 palette가 숨겨지는지 기존 테스트와 함께 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
