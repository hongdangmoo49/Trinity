# Central Agent Title Update Cache

## 배경

CentralAgentView는 markdown, local command, action 영역은 key를 비교해 변경된 경우에만 갱신한다. 하지만 title은 `apply_snapshot()`마다 `_refresh_title()`에서 같은 문자열이어도 `Static.update()`를 호출했다.

Nexus 화면은 workflow snapshot을 자주 적용하므로 idle/blueprint-ready처럼 title 문자열이 변하지 않는 상태에서는 반복 렌더 비용을 줄일 수 있다.

## 개선 방향

- CentralAgentView에 마지막 title 문자열을 저장한다.
- `_refresh_title()`은 새 title이 이전 title과 같으면 update를 생략한다.
- running spinner처럼 title 문자열이 바뀌는 경우에는 기존처럼 갱신한다.

## 범위

- `src/trinity/textual_app/widgets/central_agent.py`
- `tests/test_central_agent_view.py`

## 검증

- 같은 snapshot을 다시 적용할 때 title update가 생략되는지 확인한다.
- running 상태로 바뀌면 title spinner가 정상 표시되는지 확인한다.
- 중앙 에이전트 테스트와 전체 테스트를 통과시킨다.
