# Workspace Picker Label Update Cache

## 배경

WorkspacePicker는 preflight panel과 status label을 여러 경로에서 갱신한다. 같은 경로를 다시 입력하거나 같은 status message를 반복 설정하는 경우에도 `Static.update()`가 호출되어, 실제 화면 변화가 없는 렌더 작업이 남아 있었다.

Start/Nexus workspace label에는 이미 같은 문자열을 건너뛰는 캐시가 적용되어 있으므로, WorkspacePicker도 동일한 패턴으로 맞춘다.

## 개선 방향

- 마지막 preflight render text와 status message를 저장한다.
- preflight text가 이전과 같으면 `#workspace-preflight` update를 생략한다.
- status message가 이전과 같으면 `#workspace-picker-status` update를 생략한다.
- status/preflight 직접 update 경로를 helper로 모아 일관되게 처리한다.

## 범위

- `src/trinity/textual_app/widgets/workspace_picker.py`
- `tests/test_textual_workspace_picker.py`

## 검증

- 같은 preflight path를 다시 적용할 때 preflight panel update가 생략되는지 확인한다.
- 같은 status message를 반복 설정할 때 첫 update 이후 추가 update가 생략되는지 확인한다.
- WorkspacePicker focused test와 전체 테스트를 통과시킨다.
