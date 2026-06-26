# WP Detail Peer Review Fallback Label

## 배경

WP 상세 모달의 한국어 UI에서 리뷰가 생략됐지만 구체적인 사유가 없는 경우 `Peer review가 생략되었습니다. 신뢰도를 낮게 보세요.`처럼 영어와 한국어가 섞인 fallback 문구가 표시된다. 최근 리뷰 상태와 no-peer 사유를 한국어 표시값으로 정리했으므로, 이 fallback 문구도 자연스러운 한국어로 맞춘다.

## 목표

- 한국어 WP 상세 모달의 peer review 생략 fallback 문구를 자연스러운 한국어로 표시한다.
- 영어 UI 문구는 유지한다.
- 리뷰 summary가 있는 경우의 no-peer 사유 표시 로직은 변경하지 않는다.

## 비목표

- 리뷰 상태 저장값이나 review summary 원문은 변경하지 않는다.
- peer/no-peer 판정 규칙은 변경하지 않는다.

## 검증

- `uv run pytest tests/test_textual_app.py::test_work_package_detail_modal_keeps_korean_review_skip_fallback -q`
- `uv run pytest tests/test_textual_app.py::test_work_package_detail_modal_keeps_review_skip_fallback -q`
- `uv run pytest -q`
- `git diff --check`
- `uv run trinity --version`
