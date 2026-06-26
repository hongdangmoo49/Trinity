# Recipient Model Selection Cache

## 배경

AgentRecipientModelSelector는 Start/Nexus 화면에서 선택된 agent별 모델 값을 보관한다.
현재 `set_model_overrides()`와 `set_model_selections()`는 같은 모델 값이 다시 전달되어도
custom choice 보강과 selected model 대입 경로를 반복한다.

최근 Nexus 화면은 동일 입력을 다시 렌더링하지 않는 방향으로 최적화하고 있다. 모델 선택
복원 경로도 같은 정책을 적용하면 화면 전환, 세션 복원, provider model refresh 뒤에 같은
선택값이 반복 전달될 때 불필요한 내부 mutation을 줄일 수 있다.

## 개선 방향

- 현재 선택된 모델과 새 normalized model 값이 같으면 바로 반환한다.
- 값이 바뀐 경우에만 `_ensure_model_choice()`와 `_set_selected_model()`을 수행한다.
- `_set_selected_model()` 자체도 같은 값이면 dict write를 생략해 직접 호출 경로를 보호한다.

## 범위

- `src/trinity/textual_app/widgets/agent_recipient_model_selector.py`
- `tests/test_agent_model_choice_cache.py`

## 검증

- 같은 model selection이 반복 적용될 때 ensure/set 경로가 호출되지 않는지 확인한다.
- 같은 model override가 반복 적용될 때 ensure/set 경로가 호출되지 않는지 확인한다.
- 새 모델 값이 들어오면 기존처럼 choice 보강과 selection 갱신이 수행되는지 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
