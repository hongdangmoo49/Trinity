# Start/Nexus Model Choice Apply Cache

## 배경

StartScreen과 NexusScreen은 provider model discovery 결과를 받을 때 `set_agent_model_choices()`에서 내부 dict를 update하고, mounted 상태라면 selector에 choices를 다시 전달한다. 같은 choices가 반복 전달되는 경우에도 AgentRecipientModelSelector의 normalize/preserve-selection 경로가 다시 실행될 수 있다.

모델 discovery 결과는 앱 lifetime 중 Start/Nexus 양쪽에 반복 적용될 수 있으므로, 실제 choices가 바뀐 경우에만 selector에 전달하는 편이 낫다.

## 개선 방향

- StartScreen/NexusScreen에서 agent별 기존 choices와 새 choices를 tuple로 비교한다.
- 하나라도 변경된 경우에만 내부 dict를 갱신하고 `_apply_model_choices()`를 호출한다.
- 같은 choices 재전달은 no-op으로 처리한다.

## 범위

- `src/trinity/textual_app/screens/start.py`
- `src/trinity/textual_app/screens/nexus.py`
- `tests/test_agent_model_choice_cache.py`

## 검증

- StartScreen에서 같은 choices를 다시 적용할 때 selector 호출이 생략되는지 확인한다.
- NexusScreen에서 같은 choices를 다시 적용할 때 selector 호출이 생략되는지 확인한다.
- choices가 바뀌면 selector가 다시 호출되는지 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
