# Prompt Composer Set Text Cache

## 배경

PromptComposer의 `set_text()`는 같은 텍스트가 다시 전달되어도 `TextArea.load_text()`,
cursor 이동, command palette refresh를 반복한다. 테스트와 내부 액션에서 `set_text()`는
프롬프트 입력값을 프로그램적으로 맞출 때 자주 쓰이고, slash command palette도 이 경로에서
함께 갱신된다.

붙여넣기 placeholder 목록이 남아 있는 경우에는 같은 표시 텍스트라도 `clear_pastes=True`가
submission text를 바꾸는 의미가 있다. 따라서 paste clearing 효과가 없는 경우에만 no-op 처리해야
한다.

## 개선 방향

- `set_text()`에서 현재 TextArea text가 새 text와 같고, 지울 paste placeholder가 없으면 바로 반환한다.
- `clear_pastes=True`이고 paste placeholder가 남아 있으면 기존처럼 목록을 비우고 load/refresh 경로를 유지한다.
- text가 바뀌는 경우의 cursor 이동과 command palette refresh 동작은 유지한다.

## 범위

- `src/trinity/textual_app/widgets/composer.py`
- `tests/test_prompt_composer_palette_cache.py`

## 검증

- 같은 text를 다시 설정할 때 `TextArea.load_text()`와 palette refresh가 생략되는지 확인한다.
- paste placeholder clearing이 필요한 경우에는 같은 text라도 기존 갱신 경로가 유지되는지 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
