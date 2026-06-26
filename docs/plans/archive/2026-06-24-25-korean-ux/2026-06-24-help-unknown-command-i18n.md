# Help/Unknown 로컬 명령 한국어 라벨 개선

## 배경

`/help`, 알 수 없는 slash 명령, slash 구문 오류는 사용자가 로컬 명령을 탐색할 때 가장 먼저 보게 되는 안내다. 현재 한국어 설정에서도 제목, 설명 문구, 표 헤더가 영어로 고정되어 있다.

## 목표

- 한국어 설정에서 `/help` 제목, 설명, 카테고리 안내, 표 헤더를 한국어로 표시한다.
- 알 수 없는 명령의 제목, 본문, 추천 표 헤더를 한국어로 표시한다.
- syntax error 제목은 한국어 설정에서 한국어로 표시하되, parser가 반환하는 원문 오류는 유지한다.
- 기존 영어 기본 동작과 command registry 기반 help/추천 로직은 유지한다.

## 설계

1. `presenters.py`에 help/unknown/syntax 전용 title/body/table helper를 추가한다.
2. 기존 `help_rows(use_korean=...)`는 `lang` 인자를 받도록 확장하고 영어 기본값은 유지한다.
3. `TrinityTextualApp._handle_textual_slash_command()`의 syntax/unknown/help 분기에서 `config.lang`을 전달한다.
4. presenter 단위 테스트와 한국어 `/help`, unknown command, syntax error 경로 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "help or unknown or syntax"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
