# Answer 로컬 명령 한국어 라벨 개선

## 배경

`/answer` 명령은 인자가 없거나 `--replace`만 입력된 경우 사용법과 `/questions` 안내를 로컬 명령 결과로 보여준다. 한국어 설정에서도 이 사용법/힌트가 영어로 고정되어 로컬 명령 UX의 언어 일관성이 깨진다.

## 목표

- `/answer` 사용법 문구와 `/questions` 안내 hint를 한국어 설정에 맞게 표시한다.
- `/answer` 결과 로컬 명령의 제목은 기존처럼 command title로 유지하되, 추후 재사용 가능한 presenter helper를 둔다.
- provider/workflow가 반환하는 실제 answer 결과 메시지는 원문을 유지한다.
- 기존 영어 기본 동작은 유지한다.

## 설계

1. `presenters.py`에 answer용 usage/action hint/title helper를 추가한다.
2. `TrinityTextualApp._handle_textual_answer_command()`의 인자 누락/빈 입력 분기에서 `config.lang`을 전달한다.
3. 메시지 결과 분기의 title도 helper를 통해 동일한 라벨 경로를 사용한다.
4. presenter 단위 테스트와 한국어 `/answer` 실행 경로 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "answer"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
