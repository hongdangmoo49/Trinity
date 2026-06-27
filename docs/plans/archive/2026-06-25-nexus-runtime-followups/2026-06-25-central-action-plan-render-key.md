# Central Action Plan Render Key

## 배경

CentralAgentView는 action 영역 갱신 여부를 snapshot의 state, work package 목록, recovery 후보 등 넓은 입력값으로 판단했다. 실행 중 WP 상태가 바뀌어도 중앙 action 버튼 구성이 계속 비어 있거나 동일한 경우가 많지만, 기존 key는 이런 상태 변화까지 포함해 action title과 button container를 다시 갱신할 수 있었다.

## 개선 방향

- `central_action_plan()`의 실제 출력인 title key와 button tuple을 render key로 사용한다.
- snapshot 세부 상태가 달라져도 action plan 결과가 같으면 action 영역 재렌더를 생략한다.
- 버튼 구성이 새로 생기거나 바뀌는 경우에는 기존처럼 title과 button을 다시 mount한다.

## 범위

- `src/trinity/textual_app/widgets/central_agent.py`
- `tests/test_central_agent_view.py`

## 검증

- 실행 중 WP 상태만 바뀌고 action plan이 계속 비어 있으면 action render가 생략되는지 확인한다.
- blueprint ready로 전환되어 action plan에 버튼이 생기면 action render가 호출되는지 확인한다.
- CentralAgentView focused test와 전체 테스트를 통과시킨다.
