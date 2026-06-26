# ExecutionMatrix risk/lane 값 지역화

## 배경

ExecutionMatrix는 한국어 화면에서 헤더와 prefix를 `리스크/레인`, `리스크`로 표시하지만 값 영역에는 빈 risk fallback `unknown`과 직렬 lane `serial`이 그대로 남는다. 실행 페이지는 사용자가 WP 상태를 빠르게 훑는 핵심 화면이므로, 값 영역도 같은 언어로 맞추는 편이 낫다.

## 목표

- 한국어 UI에서 빈 risk 값을 `알 수 없음`으로 표시한다.
- 한국어 UI에서 직렬 lane 값을 `직렬`로 표시한다.
- 영어 UI의 기존 `unknown`, `serial` 표시는 유지한다.

## 작업 범위

1. ExecutionMatrix 라벨 사전에 `unknown_risk`를 추가한다.
2. `_risk_lane_label()`에 언어 인자를 추가하고 risk/lane fallback을 라벨 기반으로 렌더링한다.
3. 한국어 실행 화면 행 렌더링 테스트를 업데이트하고 빈 risk 회귀 테스트를 추가한다.

## 검증 계획

- `uv run python -m py_compile src/trinity/textual_app/screens/execution_matrix.py tests/test_textual_app.py`
- `uv run pytest tests/test_textual_app.py -k "execution_matrix_supports_korean_chrome_labels or execution_matrix_viewport_qa_matrix_with_long_workspace" -q`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest -q`
