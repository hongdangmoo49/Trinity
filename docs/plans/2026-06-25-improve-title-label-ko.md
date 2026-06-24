# Improve Title Label Korean

## 배경

`/improve` 한국어 결과 행은 상태, 심각도, 종류를 한국어 라벨로 표시하지만 action item 제목 키는 `title=Fix tests`처럼 영어 key를 그대로 사용한다. 같은 행 안에서 라벨 언어가 섞이면 후속 조치 목록을 빠르게 스캔하기 어렵다.

## 목표

- 한국어 `/improve` 행에서 `title=`을 `제목=`으로 표시한다.
- 영어 UI의 기존 `title=` 표시는 유지한다.
- action item의 실제 title/summary 텍스트는 변경하지 않는다.

## 비목표

- post-review action item 저장 구조는 변경하지 않는다.
- `/improve` 필터링, 요청 실행, action hint는 변경하지 않는다.

## 검증

- `uv run pytest tests/test_textual_app.py::test_improve_presenter_uses_korean_labels tests/test_textual_app.py::test_start_slash_improve_uses_korean_labels -q`
- `uv run pytest -q`
- `git diff --check`
- `uv run trinity --version`
