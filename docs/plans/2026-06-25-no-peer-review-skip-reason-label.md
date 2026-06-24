# No Peer Review Skip Reason Label

## 배경

한국어 UI에서 no-peer 리뷰 생략 상태는 `peer 없음`으로 표시되지만, 생략 사유는 `only codex is active; no non-owner peer reviewer is available` 같은 내부 영어 문구가 그대로 노출된다. 실행/리포트 화면의 주요 상태값을 한국어 표시값으로 정리한 흐름에 맞춰 no-peer 생략 사유도 사람이 읽기 쉬운 한국어 문장으로 변환해야 한다.

## 목표

- no-peer 리뷰 생략 사유를 표시 직전에 한국어 문장으로 변환한다.
- report screen, markdown export, WP 상세 모달에서 같은 표시 규칙을 사용한다.
- 영어 UI와 원본 snapshot 값은 유지한다.

## 비목표

- 일반 review summary의 자유 텍스트는 번역하지 않는다.
- no-peer 감지 규칙 자체는 변경하지 않는다.
- workflow/session 저장 형식은 변경하지 않는다.

## 검증

- `uv run pytest tests/test_textual_app.py::test_report_screen_uses_korean_labels tests/test_textual_app.py::test_snapshot_report_markdown_uses_korean_labels tests/test_textual_app.py::test_work_package_detail_modal_surfaces_korean_review_skip_reason -q`
- `uv run pytest -q`
- `git diff --check`
- `uv run trinity --version`
