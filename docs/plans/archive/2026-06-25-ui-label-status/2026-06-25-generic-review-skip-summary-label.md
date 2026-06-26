# Generic Review Skip Summary Label

## 배경

스냅샷 어댑터는 계획된 리뷰가 모두 생략됐지만 구체적인 사유가 없을 때 `Peer review skipped.`라는 일반 summary를 생성한다. 최근 no-peer 생략 사유와 WP 상세 fallback 문구는 한국어로 정리했지만, 이 일반 summary가 report export나 WP 상세 모달로 전달되면 한국어 화면에 영어 문장이 남을 수 있다.

## 목표

- 한국어 UI에서 일반 리뷰 생략 summary `Peer review skipped.`를 `동료 리뷰가 생략되었습니다.`로 표시한다.
- 영어 UI와 snapshot 원본 summary는 유지한다.
- no-peer 사유 변환과 review status 표시 로직은 유지한다.

## 비목표

- 임의의 review summary 자유 텍스트를 번역하지 않는다.
- 스냅샷 생성 로직이나 저장 형식은 변경하지 않는다.

## 검증

- `uv run pytest tests/test_textual_app.py::test_snapshot_report_markdown_localizes_korean_generic_review_skip_summary tests/test_textual_app.py::test_work_package_detail_modal_localizes_korean_generic_review_skip_summary -q`
- `uv run pytest -q`
- `git diff --check`
- `uv run trinity --version`
