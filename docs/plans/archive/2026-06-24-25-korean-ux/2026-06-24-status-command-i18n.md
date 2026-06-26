# Status 로컬 명령 한국어 제목 개선

## 배경

`/status` 명령의 본문과 표 컬럼은 `lang`을 전달받아 한국어 라벨을 표시하지만, 로컬 명령 결과 제목은 `"Status"`로 고정되어 있다. 한국어 UI에서 중앙 패널과 모달 제목이 영어로 보이는 작은 불일치가 남아 있다.

## 목표

- 한국어 설정에서 `/status` 결과 제목을 `상태`로 표시한다.
- 기존 영어 기본 제목은 `Status`로 유지한다.
- status markdown/rows의 기존 동작은 유지한다.

## 설계

1. `presenters.py`에 `status_title()` helper를 추가한다.
2. `TrinityTextualApp._show_textual_status()`에서 `config.lang` 기반 제목을 사용한다.
3. presenter 단위 테스트와 한국어 `/status` 앱 경로 테스트를 갱신한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "status"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
