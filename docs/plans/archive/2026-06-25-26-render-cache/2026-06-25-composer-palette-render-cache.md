# Composer Palette Render Cache

## 배경

PromptComposer의 slash command palette는 text area 변경이나 selection 이동 때 `_render_command_options()`를 호출한다. 기존 구현은 visible command option 상태가 같아도 option Static의 text, display, class를 반복 갱신했다.

slash palette는 사용자가 타이핑할 때 가장 자주 갱신되는 UI 중 하나이므로, 실제 visible option 상태가 바뀌지 않는 refresh는 no-op으로 처리하는 편이 낫다.

## 개선 방향

- visible option text, display 여부, selected class, empty class를 render key로 만든다.
- more row의 text와 display 상태도 render key에 포함한다.
- render key가 직전 key와 같으면 option update/display/class 갱신을 생략한다.
- query나 selection/window가 바뀌어 visible state가 달라지면 기존처럼 렌더한다.

## 범위

- `src/trinity/textual_app/widgets/composer.py`
- `tests/test_prompt_composer_palette_cache.py`

## 검증

- 같은 slash query refresh에서 command option update가 호출되지 않는지 확인한다.
- query가 바뀌어 visible options가 달라지면 command option update가 다시 호출되는지 확인한다.
- PromptComposer focused test와 전체 테스트를 통과시킨다.
