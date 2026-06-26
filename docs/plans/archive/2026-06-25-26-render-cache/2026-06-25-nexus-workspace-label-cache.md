# Nexus Workspace Label Update Cache

## 배경

Nexus 화면은 workflow snapshot을 적용할 때마다 action bar의 workspace label을 갱신한다. label 문자열이 바뀌지 않아도 `Static.update()`가 호출되므로, 실행 중 snapshot poll이 잦은 상황에서는 작은 렌더 작업이 반복된다.

Inspector와 CentralAgentView는 이미 값이 바뀐 경우에만 세부 영역을 갱신하는 캐시를 가지고 있다. workspace label도 같은 방식으로 맞춘다.

## 개선 방향

- `NexusScreen`에 마지막으로 표시한 workspace label 문자열을 저장한다.
- `_refresh_workspace_label()`은 새 label이 이전 label과 같으면 `Static.update()`를 호출하지 않는다.
- workspace candidate나 snapshot target workspace가 바뀌면 기존처럼 즉시 label을 갱신한다.

## 범위

- `src/trinity/textual_app/screens/nexus.py`
- `tests/test_textual_app.py`

## 검증

- workspace label이 unchanged인 경우 update 호출이 생략되는지 확인한다.
- workspace candidate가 바뀌면 label이 정상 갱신되는지 확인한다.
- 전체 테스트를 통과시킨다.
