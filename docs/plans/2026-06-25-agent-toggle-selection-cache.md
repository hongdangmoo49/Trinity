# Agent Toggle Selection Refresh Cache

## 배경

Start/Nexus 화면은 저장된 agent 선택 상태를 `AgentRecipientModelSelector.set_selected_agents()`로 재적용할 수 있다. 기존 `AgentToggle.set_value()`는 값이 실제로 바뀌지 않아도 `_refresh()`를 호출해 텍스트 update와 class 갱신을 반복했다.

agent 선택 상태가 동일한 경우에는 화면에 보이는 토글 상태도 그대로이므로 refresh를 생략할 수 있다.

## 개선 방향

- `AgentToggle.set_value()`에서 다음 선택 값을 먼저 계산한다.
- 다음 값이 현재 값과 같으면 `_refresh()`를 호출하지 않는다.
- 사용자 click/key toggle처럼 실제 값이 바뀌는 경로는 기존처럼 refresh와 changed message를 유지한다.

## 범위

- `src/trinity/textual_app/widgets/agent_recipient_model_selector.py`
- `tests/test_agent_toggle.py`

## 검증

- 같은 선택 값을 다시 적용할 때 toggle update가 생략되는지 확인한다.
- 다른 선택 값으로 바뀌면 toggle text가 정상 갱신되는지 확인한다.
- Agent toggle focused test와 전체 테스트를 통과시킨다.
