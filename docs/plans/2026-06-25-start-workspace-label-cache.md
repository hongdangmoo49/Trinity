# Start Workspace Label Update Cache

## 배경

Nexus 화면의 workspace label은 이미 같은 문자열이면 `Static.update()`를 생략하도록 캐시되어 있다. Start 화면의 `set_workspace_candidate()`는 같은 workspace candidate가 다시 전달되어도 label을 매번 update한다.

Start 화면은 실행 전 workspace 선택과 resume/preflight 경로에서 여러 번 갱신될 수 있으므로, 같은 label을 반복 갱신하지 않도록 Nexus와 동일한 패턴을 적용한다.

## 개선 방향

- StartScreen에 마지막 workspace label 문자열을 저장한다.
- 초기 compose label과 같은 값으로 캐시를 시작한다.
- `set_workspace_candidate()`에서 새 label이 이전 label과 같으면 update를 생략한다.
- candidate가 바뀌면 기존처럼 label을 갱신한다.

## 범위

- `src/trinity/textual_app/screens/start.py`
- `tests/test_start_screen.py`

## 검증

- 같은 workspace candidate를 다시 적용할 때 label update가 생략되는지 확인한다.
- 다른 candidate를 적용하면 label이 정상 갱신되는지 확인한다.
- Start screen focused test와 전체 테스트를 통과시킨다.
