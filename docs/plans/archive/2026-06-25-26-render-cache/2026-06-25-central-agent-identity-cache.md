# Central Agent View Identity Apply Cache

## 배경

CentralAgentView는 Nexus 중앙 영역에서 목표, 종합 응답, 작업 패키지 진행, 실행 상태, 후속 액션을 Markdown과 버튼으로 렌더링한다. 하위 update에는 markdown/action/local command key cache가 있지만, 같은 WorkflowNexusSnapshot 객체가 다시 전달되는 경우에도 `_markdown()`과 `central_action_plan()` 계산은 반복된다.

NexusScreen이 같은 snapshot 객체 재적용을 이미 막고 있지만, CentralAgentView는 독립 위젯 테스트와 fallback refresh 경로에서도 직접 호출될 수 있다. 위젯 내부에도 같은 객체 no-op guard를 추가하면 상위 화면 캐시가 우회되는 경우에도 불필요한 계산을 줄일 수 있다.

## 개선 방향

- CentralAgentView가 마지막으로 적용한 snapshot 객체 id를 저장한다.
- mounted 상태에서 같은 snapshot 객체가 다시 들어오면 `self.snapshot`만 유지하고 바로 반환한다.
- activity frame 갱신은 `set_activity_frame()`가 별도로 처리하므로 snapshot no-op guard와 분리한다.
- 같은 내용의 새 snapshot 객체는 기존 markdown/action/local command key cache 경로를 그대로 통과한다.

## 범위

- `src/trinity/textual_app/widgets/central_agent.py`
- `tests/test_central_agent_view.py`

## 검증

- 같은 snapshot 객체를 다시 적용할 때 `_markdown()`이 호출되지 않는지 확인한다.
- 같은 내용의 새 snapshot 객체는 기존 적용 경로를 통과하는지 확인한다.
- 기존 title/action/activity frame cache 테스트를 함께 통과시킨다.
- Focused test와 전체 테스트를 통과시킨다.
