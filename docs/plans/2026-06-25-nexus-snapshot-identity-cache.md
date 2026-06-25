# Nexus Snapshot Identity Apply Cache

## 배경

NexusSnapshotAdapter는 변경이 없으면 같은 WorkflowNexusSnapshot 객체를 반환한다. 하지만 NexusScreen.apply_snapshot()은 같은 snapshot 객체가 다시 전달되어도 provider panel, central view, question panel, inspector, workspace label, activity frame 적용 경로를 다시 호출한다.

하위 위젯에도 여러 no-op cache가 있지만, snapshot 객체가 동일한 경우에는 상위 화면에서 전체 적용을 생략하는 편이 더 가볍다.

## 개선 방향

- NexusScreen이 마지막으로 적용한 snapshot 객체 id를 저장한다.
- mounted 상태에서 같은 snapshot 객체가 다시 들어오면 `self.snapshot`만 유지하고 바로 반환한다.
- `update_provider()`처럼 snapshot 외부에서 provider panel을 임시 갱신하는 경로는 snapshot identity cache를 무효화한다.
- snapshot 내용이 같더라도 새 객체라면 기존처럼 적용한다.

## 범위

- `src/trinity/textual_app/screens/nexus.py`
- `tests/test_nexus_snapshot_identity_cache.py`

## 검증

- 같은 snapshot 객체를 다시 적용할 때 central/question/inspector refresh가 호출되지 않는지 확인한다.
- 같은 내용의 새 snapshot 객체는 기존처럼 적용되는지 확인한다.
- `update_provider()` 후 같은 snapshot 객체를 다시 적용하면 provider panel이 snapshot 상태로 복원되는지 확인한다.
- Focused test와 전체 테스트를 통과시킨다.
