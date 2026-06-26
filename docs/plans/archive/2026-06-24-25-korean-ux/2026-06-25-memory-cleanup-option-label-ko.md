# Memory Cleanup Option Label Korean

## 배경

한국어 `/memory cleanup` 오류 메시지에서 알 수 없는 옵션을 `알 수 없는 cleanup 옵션`으로 표시한다. 명령어 이름은 `/memory cleanup`으로 유지해야 하지만, 설명 라벨은 한국어 문장 안에서 자연스럽게 읽혀야 한다.

## 목표

- 한국어 오류 메시지의 `cleanup 옵션`을 `정리 옵션`으로 표시한다.
- `/memory cleanup` 명령어 표기와 실제 옵션 토큰은 유지한다.
- 영어 UI는 유지한다.

## 비목표

- cleanup 명령 이름, parser, 옵션 처리 로직은 변경하지 않는다.
- usage 문자열의 명령어/옵션 토큰은 번역하지 않는다.

## 검증

- `uv run pytest tests/test_textual_app.py::test_memory_presenter_uses_korean_labels tests/test_textual_app.py::test_nexus_memory_cleanup_error_uses_korean_message -q`
- `uv run pytest -q`
- `git diff --check`
- `uv run trinity --version`
