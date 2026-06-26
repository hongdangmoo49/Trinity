# Report 상태값 지역화

## 배경

Nexus 본 화면과 presenter 계층은 공용 status helper를 통해 한국어 UI에서 `승인`, `실패`, `대기` 같은 표시값을 사용한다. 하지만 리포트 화면과 markdown export 경로 일부는 아직 실행, 리뷰, WP 상태를 `approved`, `failed`, `pending` 같은 원시 값으로 출력한다.

## 목표

- 한국어 리포트 화면에서 WP, 실행, 리뷰, 복구 상태값을 사용자 표시값으로 렌더링한다.
- 한국어 markdown export에서도 동일한 상태 표시 규칙을 적용한다.
- 영어 UI는 기존 원시 상태값 표시를 유지한다.

## 작업 범위

1. `report_export.py`에서 work package 상태값을 `display_status_value()`로 표시한다.
2. `screens/report.py`에서 work package, execution, review, repair, recovery 상태값을 공용 helper로 표시한다.
3. 한국어 리포트/export 회귀 테스트를 추가해 상태값이 raw token으로 새지 않도록 막는다.
4. 패치 버전을 `1.0.127`로 올린다.

## 검증 계획

- `uv run python -m py_compile src/trinity/textual_app/report_export.py src/trinity/textual_app/screens/report.py tests/test_textual_app.py`
- `uv run pytest tests/test_textual_app.py -k "snapshot_report_markdown_uses_korean_labels or report_screen_uses_korean_status_labels" -q`
- `uv run pytest tests/test_textual_app.py -q`
- `uv run pytest -q`
