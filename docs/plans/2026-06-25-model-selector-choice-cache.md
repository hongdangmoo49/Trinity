# Agent Model Selector Choice Cache

## 배경

StartScreen과 NexusScreen은 provider model discovery 결과가 변하지 않으면 AgentRecipientModelSelector에 choices를 다시 전달하지 않도록 cache를 갖고 있다. 하지만 AgentRecipientModelSelector 자체는 직접 `set_model_choices()`를 호출받으면 같은 choices라도 normalize, current model 보정, selected model 갱신을 반복한다.

위젯이 screen 밖에서도 테스트와 modal 연동 경로에서 직접 쓰이므로, 위젯 내부에도 동일 choices no-op guard를 두면 상위 cache를 우회하는 호출에서도 불필요한 상태 갱신을 줄일 수 있다.

## 개선 방향

- `set_model_choices()`가 최종 normalized choices를 만든 뒤 기존 저장값과 비교한다.
- 기존 choices와 선택 모델이 이미 같으면 `_set_selected_model()` 호출 없이 반환한다.
- 현재 선택 모델이 choices에 없어서 보정 항목을 추가해야 하는 기존 동작은 유지한다.
- choices 내용이 같더라도 새 tuple/list 객체가 들어온 경우 dataclass equality로 동일성을 판단한다.

## 범위

- `src/trinity/textual_app/widgets/agent_recipient_model_selector.py`
- `tests/test_agent_model_choice_cache.py`

## 검증

- 같은 choices를 직접 다시 적용할 때 selected model 갱신이 발생하지 않는지 확인한다.
- 새 choices가 들어오면 기존처럼 저장값과 선택 모델이 갱신되는지 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
