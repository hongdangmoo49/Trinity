# Central Agent Activity Frame Cache

## 배경

CentralAgentView는 중앙 에이전트가 실행 중일 때 title에 activity frame 문자를 붙인다. Nexus activity tick은 `set_activity_frame()`을 통해 frame 값을 전달하고, CentralAgentView는 running 상태이면 title을 refresh한다.

같은 frame 값이 다시 전달되면 title 문자열도 변하지 않는다. 현재는 같은 frame에서도 `_refresh_title()`까지 호출될 수 있으므로 no-op guard를 추가해 불필요한 title update 경로를 줄인다.

## 개선 방향

- `set_activity_frame()`에서 modulo 적용 후 다음 frame 값을 계산한다.
- 다음 frame 값이 현재 `_activity_frame`과 같으면 바로 반환한다.
- frame이 바뀐 경우에만 `_activity_frame`을 갱신하고 running 상태에서 title을 refresh한다.

## 범위

- `src/trinity/textual_app/widgets/central_agent.py`
- `tests/test_central_agent_view.py`

## 검증

- running 상태에서 새 frame을 받으면 title update가 발생하는지 확인한다.
- 같은 frame을 다시 받으면 title update가 생략되는지 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
