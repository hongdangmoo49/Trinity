# Review/Improve 로컬 명령 제목 한국어 라벨 개선

## 배경

`/review`와 `/improve` 로컬 명령은 표 컬럼과 action hint는 한국어를 지원하지만, 결과 제목이 각각 `"Review"`, `"Improve"`로 고정되어 있다. 한국어 설정에서 중앙 패널의 명령 결과 제목만 영어로 남는다.

## 목표

- 한국어 설정에서 `/review` 결과 제목을 `리뷰`로 표시한다.
- 한국어 설정에서 `/improve` 결과 제목을 `개선`으로 표시한다.
- 기존 영어 기본 제목은 유지한다.
- controller가 반환하는 동적 메시지 본문은 별도 작업으로 남기고 이번 PR에서는 제목만 다룬다.

## 설계

1. `presenters.py`에 review/improve title helper를 추가한다.
2. Textual slash command 처리에서 `/review`, `/improve` 결과 제목에 helper를 사용한다.
3. 기존 한국어 경로 테스트의 기대 제목을 갱신한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "review_uses_korean_labels or improve_uses_korean_labels or review_presenter or improve_presenter"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
