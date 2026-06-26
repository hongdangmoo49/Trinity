# CentralAgentView 안내 문구 지역화

## 배경

CentralAgentView는 주요 섹션 라벨과 상태값은 한국어로 표시하지만, post-review 후속 작업 안내와 local command 다음 행동 라벨 일부가 영어로 하드코딩되어 있다. 한국어 Nexus 화면에서 사용자가 바로 따라야 하는 안내 문구가 영어로 남으면 흐름이 끊긴다.

## 목표

- 한국어 UI에서 post-review `/improve` 안내 문구를 한국어로 표시한다.
- 한국어 UI에서 local command action hint 접두어를 `_다음:_`으로 표시한다.
- 영어 UI의 기존 문구는 유지한다.

## 작업 범위

1. CentralAgentView 라벨 사전에 `improve_follow_up_hint`, `improve_done_hint`, `next`를 추가한다.
2. 하드코딩된 post-review 안내 문구와 `_Next:_` 접두어를 라벨 기반 렌더링으로 바꾼다.
3. 한국어 후속 작업 안내와 local command 다음 행동 라벨 회귀 테스트를 추가한다.

## 검증 계획

- `uv run python -m py_compile src/trinity/textual_app/widgets/central_agent.py tests/test_textual_app.py`
- `uv run pytest tests/test_textual_app.py -k "central_agent_view_localizes_korean_guidance_labels or central_agent_view_localizes_korean_status_values" -q`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest -q`
