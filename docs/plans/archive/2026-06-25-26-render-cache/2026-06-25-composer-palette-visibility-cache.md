# Composer Palette Visibility Cache

## 배경

PromptComposer는 slash command palette를 refresh할 때 `_set_command_palette_visible(True)` 또는 `False`를 반복 호출한다. option render cache가 적용되어도 visibility helper는 같은 visible 값에 대해 palette display와 `-commands-open` class를 다시 대입할 수 있다.

slash 입력 중 palette visible 상태는 대부분 유지되므로, 같은 visible 값은 no-op으로 처리하는 편이 가볍다.

## 개선 방향

- PromptComposer가 마지막 palette visible 값을 저장한다.
- `_set_command_palette_visible()`은 새 visible 값이 직전 값과 같으면 바로 반환한다.
- visible 값이 실제로 바뀌는 경우에는 기존처럼 palette display와 class를 갱신한다.

## 범위

- `src/trinity/textual_app/widgets/composer.py`
- `tests/test_prompt_composer_visibility_cache.py`

## 검증

- 같은 visible 값을 다시 적용하면 `set_class()`가 호출되지 않는지 확인한다.
- visible 값이 바뀌면 class 갱신이 호출되는지 확인한다.
- PromptComposer focused test와 전체 테스트를 통과시킨다.
