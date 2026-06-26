# Korean Slash Command Term

## 배경

한국어 help/unknown command 문구에서 `slash 명령`처럼 영어 `slash`가 그대로 남아 있다. 명령어 토큰(`/status`, `/help`)은 유지해야 하지만 설명 문장에서는 `슬래시 명령`이 더 자연스럽다.

## 목표

- 한국어 help intro/history/unknown command 문구에서 `slash 명령`을 `슬래시 명령`으로 표시한다.
- 실제 명령어 토큰과 영어 UI는 유지한다.
- Start/Nexus slash command 결과의 한국어 body 회귀 테스트를 갱신한다.

## 비목표

- 명령 parser, command registry, 명령 이름은 변경하지 않는다.
- 영어 help 문구는 변경하지 않는다.

## 검증

- `uv run pytest tests/test_textual_app.py::test_help_unknown_presenter_uses_korean_labels tests/test_textual_app.py::test_start_slash_help_uses_korean_labels tests/test_textual_app.py::test_nexus_unknown_command_uses_korean_labels -q`
- `uv run pytest -q`
- `git diff --check`
- `uv run trinity --version`
