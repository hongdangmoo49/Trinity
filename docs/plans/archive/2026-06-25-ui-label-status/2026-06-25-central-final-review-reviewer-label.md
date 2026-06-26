# Central final review reviewer label 지역화

## 배경

CentralAgentView는 한국어 UI에서 최종 리뷰 상태값을 `승인`처럼 지역화하지만, 같은 줄의 reviewer 접속어는 `by`로 남아 있다. 최종 리뷰는 사용자가 결과를 확인하는 핵심 요약 영역이므로 한국어 문맥에 맞게 표시해야 한다.

## 목표

- 한국어 UI에서 최종 리뷰 reviewer 라인을 `/ 리뷰어 ...` 형식으로 표시한다.
- 영어 UI의 기존 `by` 표시는 유지한다.
- reviewer가 비어 있을 때의 `(알 수 없음)` fallback은 유지한다.

## 작업 범위

1. CentralAgentView에 최종 리뷰 라인 렌더링 helper를 추가한다.
2. 한국어/영어 라벨 사전에 `reviewer`를 추가한다.
3. 기존 한국어/영어 최종 리뷰 테스트 기대값을 갱신한다.

## 검증 계획

- `uv run python -m py_compile src/trinity/textual_app/widgets/central_agent.py tests/test_textual_app.py`
- `uv run pytest tests/test_textual_app.py -k "central_agent_view_localizes_korean_status_values or central_agent_view_keeps_english_status_values" -q`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest -q`
