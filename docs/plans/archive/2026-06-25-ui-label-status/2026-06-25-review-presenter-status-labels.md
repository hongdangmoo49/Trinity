# Review presenter 상태값 지역화

## 배경

Nexus 중앙 패널과 실행 화면의 리뷰 상태값은 한국어 UI에서 `승인`, `변경 요청`, `peer 없음`처럼 표시된다. 하지만 `/review` 로컬 명령 presenter와 context markdown의 최종 리뷰 줄은 아직 `approved` 같은 원시 상태값을 그대로 출력한다.

## 목표

- 한국어 `/review` 결과의 리뷰된 WP와 최종 리뷰 상태값을 지역화한다.
- 한국어 context markdown의 최종 리뷰 상태값을 지역화한다.
- 영어 UI의 기존 raw 상태 표시는 유지한다.

## 작업 범위

1. presenter 레이어에서 공용 `display_review_status_value()` helper를 사용한다.
2. `review_rows()`의 리뷰된 WP/최종 리뷰 값에 지역화 상태값을 적용한다.
3. `snapshot_context_markdown()`의 최종 리뷰 줄에 지역화 상태값을 적용한다.
4. 기존 한국어 presenter 회귀 테스트 기대값을 갱신한다.

## 검증 계획

- `uv run python -m py_compile src/trinity/textual_app/presenters.py tests/test_textual_app.py`
- `uv run pytest tests/test_textual_app.py -k "review_presenter_uses_korean_labels or context_markdown_uses_korean_labels" -q`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest -q`
