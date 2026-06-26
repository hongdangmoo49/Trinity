# Central Running Class Cache

## 배경

CentralAgentView는 snapshot을 적용할 때마다 현재 workflow가 실행 중인지 계산하고
`central-running` class를 동기화한다. snapshot identity cache가 같은 객체 재적용은 막지만,
새 snapshot 객체가 같은 running 상태를 유지하는 경우에도 `set_class()`는 반복 호출된다.

Nexus 페이지는 provider 상태, 질문, 실행 로그 등 여러 투영값을 자주 갱신한다. 중앙 에이전트
뷰의 running class도 실제 상태가 바뀔 때만 class mutation을 수행하면 화면 갱신 비용을 더
일관되게 줄일 수 있다.

## 개선 방향

- CentralAgentView에 마지막 running class 상태를 캐시한다.
- snapshot 적용 시 running 여부가 바뀐 경우에만 `central-running` class를 동기화한다.
- activity frame에 따른 title 업데이트와 markdown/action rendering cache는 기존 동작을 유지한다.

## 범위

- `src/trinity/textual_app/widgets/central_agent.py`
- `tests/test_central_agent_view.py`

## 검증

- 서로 다른 snapshot 객체라도 running 여부가 같으면 `central-running` class sync가 생략되는지 확인한다.
- running 상태에서 idle 상태로 바뀌면 기존처럼 class가 해제되는지 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
