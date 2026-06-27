# Central Agent Activity Frame Running-Only Update

## 배경

Nexus 실행 화면은 provider panel과 central agent title에 activity frame을 주기적으로 전달한다. Central Agent title은 실행 중일 때만 frame 문자를 표시하지만, 기존 `set_activity_frame()`은 idle, blueprint ready, done 상태에서도 매 tick마다 title `Static.update()`를 호출했다.

이 경우 화면에 보이는 텍스트는 변하지 않는데도 Textual 위젯 갱신이 반복되어, 긴 실행 세션 이후 Nexus 화면의 불필요한 렌더 비용이 누적될 수 있다.

## 개선 방향

- `CentralAgentView.set_activity_frame()`은 내부 `_activity_frame` 값은 항상 최신으로 유지한다.
- 단, title 갱신은 `_is_running()`이 true인 상태에서만 수행한다.
- snapshot이 바뀌는 순간에는 기존 `apply_snapshot()`이 `_refresh_title()`을 호출하므로 idle/running 전환 표시가 지연되지 않는다.

## 범위

- `src/trinity/textual_app/widgets/central_agent.py`
- `tests/test_central_agent_view.py`

## 검증

- idle/blueprint-ready 상태에서 activity frame tick이 title update를 호출하지 않는지 확인한다.
- executing 상태에서는 activity frame tick이 기존처럼 title spinner를 갱신하는지 확인한다.
- 기존 중앙 에이전트 markdown/presenter 테스트와 전체 테스트를 통과시킨다.
