# Textual Launch CWD Helper

## 목적

`TrinityTextualApp`에 남아 있는 실행 위치 기본값 계산을 target workspace helper로 분리해 workspace 흐름의 순수 로직을 앱 바깥에서 검증할 수 있게 한다.

## 범위

- `default_launch_cwd()` helper를 `textual_app.target_workspace`에 추가한다.
- `TrinityTextualApp`은 helper를 호출만 하도록 정리한다.
- `Path.cwd().resolve()` 실패 시 기존처럼 best-effort expanduser 경로를 반환한다.
- 패치 버전을 `1.0.428`로 올린다.

## 비목표

- workspace picker UI나 preflight 흐름은 변경하지 않는다.
- target workspace 생성/확인 정책은 변경하지 않는다.

## 검증

- target workspace helper focused test를 보강한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.428`을 출력해야 한다.
