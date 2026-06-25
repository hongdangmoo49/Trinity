# Nexus Initial Prompt Refresh Cache

## 배경

NexusScreen은 Start 화면이나 resume 흐름에서 `set_initial_prompt()`를 통해 초기 prompt를 받는다. 현재는 prompt를 `strip()`한 뒤 항상 `initial_prompt`에 저장하고, 화면이 mounted 상태이면 중앙 영역을 refresh한다.

같은 prompt가 공백만 다르게 다시 전달되는 경우 fallback snapshot과 중앙 영역 내용은 변하지 않는다. 이 경우 `_refresh_central()` 호출을 생략해 불필요한 Markdown/projection 계산을 줄일 수 있다.

## 개선 방향

- `set_initial_prompt()`에서 normalized prompt를 먼저 계산한다.
- normalized prompt가 기존 `initial_prompt`와 같으면 바로 반환한다.
- prompt가 바뀐 경우에만 값을 갱신하고 mounted 상태에서 `_refresh_central()`을 호출한다.

## 범위

- `src/trinity/textual_app/screens/nexus.py`
- `tests/test_nexus_initial_prompt_cache.py`

## 검증

- 같은 prompt가 다시 설정될 때 중앙 refresh가 호출되지 않는지 확인한다.
- 다른 prompt가 설정되면 중앙 refresh가 호출되는지 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
