# Start Workspace Candidate Setter Cache

## 배경

StartScreen은 `set_workspace_candidate()`에서 workspace candidate를 저장한 뒤 label widget을 조회하고, label text가 바뀐 경우에만 update한다. 기존 label cache 덕분에 같은 text update는 생략되지만, 같은 candidate가 반복 전달되는 경우에도 widget query와 label 계산은 발생한다.

NexusScreen에는 동일 workspace candidate 재적용 guard가 추가되어 있다. StartScreen도 같은 정책을 적용하면 Start 화면에서 workspace picker 결과나 route refresh가 같은 candidate를 다시 전달할 때 더 가볍게 처리할 수 있다.

## 개선 방향

- `set_workspace_candidate()`에서 새 path가 기존 `workspace_candidate`와 같으면 바로 반환한다.
- path가 바뀐 경우에만 기존처럼 label widget을 조회하고 label cache/update 경로를 수행한다.
- 기존 `_workspace_label_key` 기반 text update cache는 유지한다.

## 범위

- `src/trinity/textual_app/screens/start.py`
- `tests/test_start_screen.py`

## 검증

- 같은 workspace candidate가 다시 설정될 때 label widget query가 발생하지 않는지 확인한다.
- 다른 workspace candidate가 설정되면 기존처럼 label update가 발생하는지 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
