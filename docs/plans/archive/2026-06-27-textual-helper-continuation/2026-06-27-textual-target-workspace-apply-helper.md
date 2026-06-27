# Textual Target Workspace Apply Helper

## 목적

`TrinityTextualApp._set_textual_target_workspace()`에 남아 있는 target workspace 성공 적용 책임을 내부 helper로 분리해 slash command 흐름을 더 얇게 만든다.

## 범위

- target workspace 준비 실패 처리는 기존 함수에 유지한다.
- 준비가 끝난 `resolved_path`를 workflow controller에 적용하고, snapshot/preflight 기억, workspace candidate 동기화, `/target` 결과 표시를 처리하는 helper를 추가한다.
- 기존 성공/실패 메시지, control repo 확인 값, candidate 동기화 순서는 유지한다.
- 패치 버전을 `1.0.434`로 올린다.

## 비목표

- target workspace prepare 정책, creatable probe, control repo 확인 modal 정책은 변경하지 않는다.
- `TextualWorkflowController.set_target_workspace()`의 반환 계약은 변경하지 않는다.
- Nexus 화면 레이아웃이나 presenter 문구는 변경하지 않는다.

## 검증

- target workspace 관련 Textual app focused test를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.434`를 출력해야 한다.
