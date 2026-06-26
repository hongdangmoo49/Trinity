# Compact WP 담당자 fallback 지역화

## 배경

Inspector와 CentralAgentView는 `compact_wp_line()` helper로 현재/다음/차단 WP를 한 줄로 표시한다. 이 helper는 담당자 정보가 비어 있으면 `unassigned`를 직접 사용하므로, 한국어 UI에서도 `Unassigned`가 노출될 수 있다.

## 목표

- 한국어 UI에서 담당자 fallback을 `미지정`으로 표시한다.
- 영어 UI의 기존 fallback 의미는 유지한다.
- Inspector와 CentralAgentView가 같은 helper를 쓰는 구조를 유지한다.

## 작업 범위

1. `compact_wp_line()`에 `lang` 인자를 추가한다.
2. Inspector와 CentralAgentView 호출부에서 현재 UI 언어를 전달한다.
3. 한국어 Inspector 회귀 테스트에서 담당자 미지정 WP가 `미지정`으로 표시되는지 확인한다.

## 검증 계획

- `uv run python -m py_compile src/trinity/textual_app/widgets/progress_summary.py src/trinity/textual_app/widgets/inspector.py src/trinity/textual_app/widgets/central_agent.py tests/test_textual_app.py`
- `uv run pytest tests/test_textual_app.py -k "workflow_inspector_uses_configured_korean_labels" -q`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest -q`
