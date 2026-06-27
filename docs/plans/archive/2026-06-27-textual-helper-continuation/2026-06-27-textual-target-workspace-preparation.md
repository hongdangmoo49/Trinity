# Textual Target Workspace Preparation

## 목적

`TrinityTextualApp._set_textual_target_workspace()`에 남아 있는 대상 작업 폴더 준비 로직을 helper로 분리해 파일 충돌, 디렉터리 생성, resolve 실패 처리를 앱 바깥에서 검증한다.

## 범위

- target workspace 준비 결과를 표현하는 작은 dataclass를 추가한다.
- 기존 동작처럼 파일 경로는 `not_directory`, mkdir/resolve `OSError`는 `os_error`로 반환한다.
- 앱은 helper 결과에 따라 기존 warning 메시지를 기록하거나 resolved target을 workflow controller에 전달한다.
- 패치 버전을 `1.0.429`로 올린다.

## 비목표

- target workspace 확인 modal, control repo 확인 정책은 변경하지 않는다.
- workspace picker UI와 preflight 흐름은 변경하지 않는다.

## 검증

- target workspace preparation focused test를 보강한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.429`를 출력해야 한다.
