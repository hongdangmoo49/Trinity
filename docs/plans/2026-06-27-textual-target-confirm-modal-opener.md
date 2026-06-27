# Textual Target Confirm Modal Opener

## 목적

control repo target 확인이 필요한 workspace/target 흐름에서 반복되는 `TargetWorkspaceConfirmModal` 생성 패턴을 앱 내부 helper로 분리한다.

## 범위

- target path와 callback을 받아 confirmation modal을 여는 `_open_target_workspace_confirm_modal()` helper를 추가한다.
- Nexus workspace 선택, execution preflight 선택, `/target` 명령의 control repo 확인 분기가 같은 helper를 사용하게 정리한다.
- 기존 modal 문구, callback, 확인/취소 후 동작은 변경하지 않는다.
- 패치 버전을 `1.0.431`로 올린다.

## 비목표

- control repo 판정 로직은 변경하지 않는다.
- target cancellation presenter나 target preparation helper는 변경하지 않는다.
- workspace picker UI는 변경하지 않는다.

## 검증

- target confirmation 관련 Textual app focused test를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.431`을 출력해야 한다.
