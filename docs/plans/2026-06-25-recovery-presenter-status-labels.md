# Recovery presenter 상태값 지역화

## 배경

한국어 Nexus UI의 대부분 상태값은 공용 status helper를 통해 `변경 요청`, `복구 차단`, `중단`처럼 표시된다. 하지만 review-repair와 execution-recovery presenter는 아직 `changes_requested`, `repair_blocked` 같은 원시 값을 한국어 문장 안에 그대로 섞어 출력한다.

## 목표

- `/review-repair` 표와 상세 본문에서 리뷰/복구 상태값을 한국어 표시값으로 렌더링한다.
- `/execute-recovery` 표와 markdown에서 recovery state를 한국어 표시값으로 렌더링한다.
- 영어 UI는 기존 raw 상태 표시를 유지한다.

## 작업 범위

1. presenter 레이어에서 `display_review_status_value()`와 `display_status_value()`를 재사용한다.
2. review-repair rows의 리뷰 상태와 recovery-only 상태를 지역화한다.
3. execution-recovery rows/markdown의 실행 상태를 지역화한다.
4. 관련 presenter 테스트 기대값을 보강한다.
5. 패치 버전을 `1.0.128`로 올린다.

## 검증 계획

- `uv run python -m py_compile src/trinity/textual_app/presenters.py tests/test_textual_app.py`
- `uv run pytest tests/test_textual_app.py -k "execute_presenter_uses_korean_labels or review_repair_details" -q`
- `uv run pytest tests/test_textual_app.py -q`
- `uv run pytest -q`
