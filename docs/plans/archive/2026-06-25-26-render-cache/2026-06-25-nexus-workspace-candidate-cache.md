# Nexus Workspace Candidate Refresh Cache

## 배경

NexusScreen은 workflow target workspace가 아직 없을 때 `set_workspace_candidate()`로 fallback workspace path를 받아 화면 label을 갱신한다. `_refresh_workspace_label()`에는 label text cache가 있지만, 같은 candidate가 반복 전달되면 상위 화면은 여전히 label refresh 경로를 호출한다.

같은 candidate 문자열이 다시 들어오는 경우 화면 상태는 변하지 않는다. 이 경우 상위 setter에서 바로 반환해 불필요한 label 계산과 query 경로를 줄일 수 있다.

## 개선 방향

- `set_workspace_candidate()`에서 다음 candidate 문자열을 먼저 계산한다.
- 다음 candidate가 기존 `_workspace_candidate`와 같으면 바로 반환한다.
- 값이 바뀐 경우에만 `_workspace_candidate`를 갱신하고 mounted 상태에서 `_refresh_workspace_label()`을 호출한다.

## 범위

- `src/trinity/textual_app/screens/nexus.py`
- `tests/test_nexus_workspace_candidate_cache.py`

## 검증

- 같은 workspace candidate가 다시 설정될 때 `_refresh_workspace_label()`이 호출되지 않는지 확인한다.
- 다른 workspace candidate가 설정되면 기존처럼 refresh가 호출되는지 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
