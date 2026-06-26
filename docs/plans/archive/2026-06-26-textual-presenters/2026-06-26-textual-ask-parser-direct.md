# Textual Ask Parser Direct Use

## 배경

`TrinityTextualApp._parse_ask_args`는 `trinity.textual_app.command_parsers.parse_ask_args`의 결과 객체를 다시 tuple로 풀어 반환하는 delegate였다. TextualApp에서 순수 파서를 직접 사용하면 slash command parsing 책임이 더 분명해지고 앱 내부 wrapper가 하나 줄어든다.

plain TUI의 `/ask` 파서는 현재 에러 문구가 Textual 파서와 다르므로 이번 작업에서는 변경하지 않는다.

## 목표

- TextualApp에서 `parse_ask_args` 결과 객체를 직접 사용한다.
- `_parse_ask_args` wrapper를 제거한다.
- `/ask`의 대상 에이전트, 모델 override, prompt, localized error 동작은 유지한다.
- 패치 버전을 `1.0.327`로 올린다.

## 변경 계획

1. `_handle_textual_ask_command`에서 `parse_ask_args`를 직접 호출한다.
2. `AskCommandParseResult` 필드를 그대로 사용해 start/follow-up 흐름에 전달한다.
3. `_parse_ask_args` method를 삭제한다.
4. 기존 command parser/TextualApp 테스트로 회귀를 확인한다.

## 검증

- `git diff --check`
- `uv run trinity --version`
- `uv run pytest -q tests/test_textual_app.py tests/test_textual_command_parsers.py tests/test_slash_commands.py`
- `uv run pytest -q`
