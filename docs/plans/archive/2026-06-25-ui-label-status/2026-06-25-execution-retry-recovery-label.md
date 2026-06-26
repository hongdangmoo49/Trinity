# Execution Retry Recovery State Label

## 배경

실행 재시도 모달은 한국어 chrome과 상태 셀을 지원하지만, 요약 줄의 recovery state는 `복구: failed`처럼 원본 상태값을 그대로 표시한다. 한국어 UI에서는 `복구: 실패`처럼 기존 상태 라벨 체계를 따라야 한다.

## 목표

- `ExecutionRetryModal._summary_text()`의 recovery state를 표시용 상태 라벨로 렌더링한다.
- recovery snapshot이 없거나 state가 비어 있을 때는 기존 placeholder 라벨을 사용한다.
- 영어 UI와 snapshot 원본값은 유지한다.

## 비목표

- execution recovery snapshot 저장 형식은 변경하지 않는다.
- 재시도 selector/filter 동작은 변경하지 않는다.
- recovery 상세 문구 전체 재작성은 하지 않는다.

## 검증

- `uv run pytest tests/test_textual_app.py::test_execution_retry_modal_supports_korean_chrome_labels -q`
- `uv run pytest -q`
- `git diff --check`
- `uv run trinity --version`
