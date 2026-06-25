# Provider Panel Field-Level Updates

## 배경

ProviderPanel은 provider 상태가 바뀔 때 name, meta, status, summary 네 영역을 모두 갱신한다. 실제 실행 중에는 status만 `Running`에서 `Ready`로 바뀌거나, activity frame으로 status만 바뀌는 경우가 많다.

패널 전체 state가 달라졌다는 이유로 변경되지 않은 child 위젯까지 `Static.update()`를 호출하면 snapshot poll과 provider 상태 전환이 잦은 Nexus 화면에서 불필요한 렌더 비용이 생긴다.

## 개선 방향

- `update_state()`에서 이전 렌더 문자열과 새 렌더 문자열을 비교한다.
- name, meta, status, summary 중 실제 문자열이 달라진 child만 갱신한다.
- class 갱신은 provider state group 표시를 위해 기존처럼 유지한다.

## 범위

- `src/trinity/textual_app/widgets/provider_panel.py`
- `tests/test_provider_panel.py`

## 검증

- provider status만 바뀐 경우 status field만 update되는지 확인한다.
- 기존 activity frame 테스트와 전체 테스트를 통과시킨다.
