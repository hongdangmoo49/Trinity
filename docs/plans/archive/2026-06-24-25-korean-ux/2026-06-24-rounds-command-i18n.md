# Rounds 로컬 명령 한국어 라벨 개선

## 배경

`/rounds` 명령은 현재 최대 라운드 조회, 세션 한정 변경, 숫자/범위 오류를 Nexus 로컬 명령 결과로 보여준다. 한국어 설정에서도 제목, 본문, action hint, 표 헤더와 행 라벨이 영어로 고정되어 있다.

## 목표

- 한국어 설정에서 `/rounds` 조회/변경/오류 결과를 한국어로 표시한다.
- 현재 최대 라운드와 허용 범위 표 라벨을 한국어화한다.
- 기존 영어 기본 동작과 세션 한정 설정 로직은 유지한다.

## 설계

1. `presenters.py`에 rounds 전용 title/body/action hint/table helper를 추가한다.
2. `TrinityTextualApp._handle_textual_rounds_command()`에서 고정 문자열 대신 helper에 `config.lang`을 전달한다.
3. presenter 단위 테스트와 한국어 `/rounds` 조회/변경/오류 경로 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "rounds"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
