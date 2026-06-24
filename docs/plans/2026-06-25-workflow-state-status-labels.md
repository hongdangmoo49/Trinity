# Workflow state 상태값 지역화

## 배경

작업 패키지, 리뷰, 복구 상태값은 한국어 UI에서 공용 status helper를 통해 `완료`, `대기`, `변경 요청`처럼 표시된다. 하지만 최상위 workflow state는 `/status`, `/workflow`, `/context`, Inspector, report 화면에서 아직 `blueprint_ready`, `post_review_ready`, `needs_user_decision` 같은 raw token으로 남아 있다.

## 목표

- 한국어 UI의 최상위 workflow state를 사용자 표시값으로 렌더링한다.
- presenter, report export, report screen, Workflow Inspector가 같은 공용 label을 사용하도록 맞춘다.
- 영어 UI는 기존 raw state 표시를 유지한다.

## 작업 범위

1. `display_status_value()`의 한국어 workflow state label을 보강한다.
2. Textual presenter의 workflow state 출력 지점에 `_status_value()`를 적용한다.
3. report export/report screen/Workflow Inspector의 state 표시를 공용 helper로 맞춘다.
4. 관련 한국어 테스트 기대값을 갱신한다.
5. 패치 버전을 `1.0.132`로 올린다.

## 검증 계획

- `uv run python -m py_compile src/trinity/textual_app/presenters.py src/trinity/textual_app/report_export.py src/trinity/textual_app/screens/report.py src/trinity/textual_app/widgets/inspector.py tests/test_textual_app.py`
- `uv run pytest tests/test_textual_app.py -k "status_presenter_uses_korean_labels or workflow_presenter_uses_korean_labels or context_markdown_uses_korean_labels or report_screen_snapshot_uses_korean_body_labels or workflow_inspector_uses_configured_korean_labels" -q`
- `uv run pytest tests/test_textual_app.py -q`
- `uv run pytest -q`
