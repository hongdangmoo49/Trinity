# Progress summary unknown 표기 통일

## 배경

Nexus와 실행 화면의 여러 fallback은 한국어에서 `알 수 없음`을 사용한다. 하지만 compact progress summary의 unknown bucket만 `알수없음`으로 붙여 표기되어 같은 화면 안에서 용어가 미세하게 어긋난다.

## 목표

- 한국어 progress summary unknown bucket을 `알 수 없음`으로 통일한다.
- 영어 summary 출력은 유지한다.
- Inspector progress summary에서 unknown bucket이 포함될 때 회귀 테스트로 확인한다.

## 작업 범위

1. `progress_summary_line()`의 한국어 unknown 라벨을 수정한다.
2. 한국어 `WorkflowInspector` 테스트에 unknown 상태 WP를 추가한다.

## 검증 계획

- `uv run python -m py_compile src/trinity/textual_app/widgets/progress_summary.py tests/test_textual_app.py`
- `uv run pytest tests/test_textual_app.py -k "workflow_inspector_uses_configured_korean_labels or central_agent_view_localizes_korean_execution_progress" -q`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest -q`
