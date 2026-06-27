# Textual Workspace Picker Factory

## 목적

`TrinityTextualApp._open_workspace_picker()`에 남아 있는 `WorkspacePicker` 생성 인자 조립을 widget helper로 분리해 workspace picker 생성 정책을 앱 바깥에서 검증한다.

## 범위

- `build_workspace_picker()` helper를 `widgets.workspace_picker`에 추가한다.
- helper는 candidate, lang, snapshot, control repo cwd, tree root, intent를 기존과 동일하게 구성한다.
- `TrinityTextualApp`은 helper로 생성된 picker를 push만 하도록 정리한다.
- 패치 버전을 `1.0.432`로 올린다.

## 비목표

- workspace picker UI, preflight 계산, confirm/cancel callback 흐름은 변경하지 않는다.
- target workspace 설정 정책은 변경하지 않는다.

## 검증

- workspace picker factory focused test를 추가한다.
- workspace picker 관련 focused test를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.432`를 출력해야 한다.
