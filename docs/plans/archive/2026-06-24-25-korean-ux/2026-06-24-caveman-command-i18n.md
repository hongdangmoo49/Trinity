# Caveman 로컬 명령 한국어 라벨 개선

## 배경

`/caveman` 명령은 간결 응답 모드의 현재 상태 조회와 세션 한정 변경을 로컬 명령 결과로 보여준다. 한국어 설정에서도 제목, 본문, action hint, 표 헤더와 행 라벨이 영어로 고정되어 있다.

## 목표

- 한국어 설정에서 `/caveman` 조회/변경/사용법 오류 결과를 한국어로 표시한다.
- `Mode`, `Intensity`, `Allowed` 행 라벨과 표 헤더를 한국어화한다.
- 기존 영어 기본 동작과 caveman 설정 로직은 유지한다.

## 설계

1. `presenters.py`에 caveman 전용 title/body/action hint/table helper를 추가한다.
2. `TrinityTextualApp._handle_textual_caveman_command()`에서 helper에 `config.lang`을 전달한다.
3. presenter 단위 테스트와 한국어 `/caveman` 조회/변경/오류 경로 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "caveman"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
