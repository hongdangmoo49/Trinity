# Nexus Agent Selection Apply Cache

## 배경

NexusScreen은 Start 화면 전환이나 resume 흐름에서 `set_agent_selection()`으로 대상 agent와 model override를 받는다. 현재는 같은 선택 상태가 다시 전달되어도 내부 상태를 덮어쓰고 `_apply_agent_selection()`을 호출한다.

AgentRecipientModelSelector에도 일부 no-op guard가 있지만, 같은 선택 상태라면 NexusScreen 상위에서 selector 적용 자체를 생략할 수 있다.

## 개선 방향

- `set_agent_selection()`에서 target agents tuple과 model overrides dict를 먼저 정규화한다.
- 정규화한 값이 기존 `_selected_agents`, `_agent_model_overrides`와 같으면 바로 반환한다.
- 값이 바뀐 경우에만 내부 상태를 갱신하고 mounted 상태에서 `_apply_agent_selection()`을 호출한다.

## 범위

- `src/trinity/textual_app/screens/nexus.py`
- `tests/test_nexus_agent_selection_cache.py`

## 검증

- 같은 agent/model override 선택이 다시 들어올 때 `_apply_agent_selection()`이 호출되지 않는지 확인한다.
- 다른 agent 선택이 들어오면 기존처럼 `_apply_agent_selection()`이 호출되는지 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
