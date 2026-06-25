# Nexus Activity Frame Target Gate

## 배경

최근 변경으로 ProviderPanel과 CentralAgentView는 실행 중 상태에서만 activity frame으로 화면을 갱신한다. 다만 상위 `NexusScreen.advance_activity_frame()`은 workflow poll tick마다 frame을 증가시키고 모든 activity 대상에게 호출을 전달한다.

하위 위젯에서 실제 렌더 갱신은 피하더라도, idle/blueprint-ready/done 상태에서 screen이 계속 frame을 전파하면 불필요한 query와 메서드 호출이 남는다.

## 개선 방향

- `NexusScreen.advance_activity_frame()` 진입 시 실제 activity 표시 대상이 있는지 먼저 확인한다.
- 중앙 에이전트나 provider panel 중 하나라도 running activity를 표시할 때만 frame을 증가시키고 하위 위젯에 전달한다.
- 각 위젯은 `has_running_activity()`로 자신의 표시 필요 여부를 노출한다.

## 범위

- `src/trinity/textual_app/screens/nexus.py`
- `src/trinity/textual_app/widgets/provider_panel.py`
- `src/trinity/textual_app/widgets/central_agent.py`
- `tests/test_textual_app.py`

## 검증

- Nexus 화면에 실행 중 surface가 없으면 `advance_activity_frame()`이 frame 값을 변경하지 않고 하위 위젯 호출도 생략하는지 확인한다.
- 실행 중 provider/central surface는 기존처럼 spinner가 갱신되는지 기존 테스트로 확인한다.
- 전체 테스트를 통과시킨다.
