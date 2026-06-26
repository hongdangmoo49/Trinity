# Nexus Provider State Cache

## 배경

NexusScreen은 snapshot을 받을 때마다 각 provider에 대해 ProviderPanelState를 만들고, 해당 panel을 query한 뒤 `update_state()`를 호출한다. ProviderPanel 내부에도 동일 state를 조기 반환하는 방어가 있지만, 상위 화면에서는 동일 provider state에도 lookup과 method call이 반복된다.

실행 중 poll 주기가 짧고 provider 상태가 자주 유지되는 구간에서는 상위 화면에서 동일 state를 먼저 걸러내는 편이 가볍다.

## 개선 방향

- NexusScreen이 agent별 마지막 ProviderPanelState를 저장한다.
- snapshot provider state가 직전 state와 같으면 panel query와 `update_state()` 호출을 생략한다.
- `update_provider()`로 직접 provider 상태를 바꾸는 경로도 같은 cache를 갱신한다.

## 범위

- `src/trinity/textual_app/screens/nexus.py`
- `tests/test_nexus_provider_state_cache.py`

## 검증

- 같은 provider snapshot을 다시 적용하면 ProviderPanel.update_state가 호출되지 않는지 확인한다.
- provider status가 바뀌면 update_state가 정상 호출되는지 확인한다.
- Nexus provider cache focused test와 전체 테스트를 통과시킨다.
