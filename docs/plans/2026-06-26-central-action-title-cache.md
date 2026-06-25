# Central Action Title Cache

## 배경

CentralAgentView는 blueprint/repair/provider-error 액션 버튼 구성이 바뀔 때
`_render_blueprint_actions()`로 액션 영역을 다시 렌더링한다. 이때 action title은 버튼 구성이
바뀌더라도 같은 문자열인 경우가 많지만, 현재는 매번 `#central-action-title`을 조회하고
`Static.update()`를 호출한다.

액션 버튼 컨테이너는 버튼 구성이 바뀌면 다시 그려야 하지만, 제목 텍스트는 별도 render key로
관리할 수 있다. 이렇게 분리하면 중앙 에이전트 영역의 반복 UI mutation을 더 줄일 수 있다.

## 개선 방향

- CentralAgentView에 마지막 action title 문자열을 캐시한다.
- `_render_blueprint_actions()`는 title helper를 통해 문자열이 바뀐 경우에만 update한다.
- 버튼 컨테이너 remove/mount와 button action mapping은 기존 동작을 유지한다.
- 버튼이 없는 plan에서는 title을 빈 문자열로 동기화하되, 이미 비어 있으면 update를 생략한다.

## 범위

- `src/trinity/textual_app/widgets/central_agent.py`
- `tests/test_central_agent_view.py`

## 검증

- 같은 title의 다른 button plan을 렌더링할 때 action title update가 생략되는지 확인한다.
- button plan이 빈 상태로 바뀌면 기존처럼 title이 비워지는지 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
