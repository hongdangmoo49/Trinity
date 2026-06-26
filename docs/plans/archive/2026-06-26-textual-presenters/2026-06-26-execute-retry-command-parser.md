# Execute Retry Command Parser Refactor

## 배경

`/execute-retry` 인자 파싱 규칙이 TextualApp과 plain TUI 세션에 각각 같은 형태로 남아 있었다. 두 UI는 같은 slash command registry를 공유하므로 selector 해석 규칙도 한 곳에서 관리하는 것이 맞다.

## 목표

- `/execute-retry [all|failed|blocked|interrupted|custom|WP-ID...]` 파싱 규칙을 공용 함수로 분리한다.
- TextualApp과 plain TUI가 같은 파서를 호출하게 한다.
- 기존 동작을 유지한다.
  - 인자가 없으면 `("all", [])`
  - 첫 인자가 알려진 selector면 selector와 나머지 package id
  - 그 외에는 `("custom", args)`
- 파서 단위 테스트를 추가해 이후 selector 변경 시 회귀를 빨리 잡는다.

## 변경 계획

1. `trinity.slash_commands`에 `parse_execute_retry_args`를 추가한다.
2. `TrinityTextualApp._parse_execute_retry_args`와 `TrinitySession._parse_execute_retry_args`를 제거한다.
3. 양쪽 호출부를 공용 파서로 교체한다.
4. `tests/test_slash_commands.py`에 selector/default/custom 케이스를 추가한다.
5. 패치 버전을 `1.0.324`로 올린다.

## 검증

- `git diff --check`
- `uv run trinity --version`
- `uv run pytest -q tests/test_slash_commands.py tests/test_textual_app.py tests/test_tui_session.py`
- `uv run pytest -q`
