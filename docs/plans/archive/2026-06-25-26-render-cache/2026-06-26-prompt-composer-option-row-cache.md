# Prompt Composer Option Row Cache

## 배경

PromptComposer는 slash command palette 전체 render key가 같으면 렌더링을 생략한다. 하지만
선택 항목만 위아래로 이동하는 경우에는 전체 render key가 바뀌고, 모든 option row에 대해
label update, display 설정, selected/empty class 동기화를 다시 수행한다.

선택 이동 시 실제로 바뀌는 row는 이전 selected row와 새 selected row뿐이다. 나머지 row는
label, display, empty 상태가 그대로이므로 widget query와 mutation을 줄일 수 있다.

## 개선 방향

- command option row별 render key를 저장한다.
- row 상태가 바뀐 경우에만 해당 `#command-option-N` widget을 조회하고 update/display/class를
  동기화한다.
- more indicator도 별도 render key로 관리해 텍스트/표시 여부가 바뀐 경우에만 갱신한다.
- palette 전체 render key는 유지해 완전히 같은 렌더 호출은 기존처럼 빠르게 반환한다.

## 범위

- `src/trinity/textual_app/widgets/composer.py`
- `tests/test_prompt_composer_palette_cache.py`

## 검증

- 선택 항목만 이동할 때 option label update가 발생하지 않는지 확인한다.
- 선택 이동 시 변경된 option row만 조회되는지 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
