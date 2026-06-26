# Textual Local Command Presenter 분리 설계

## 배경

`TrinityTextualApp._local_command_snapshot()`은 local slash command 결과를 `LocalCommandSnapshot`으로 포장하는 순수 presenter helper다. 현재 앱 본문에 남아 있어 local command 표시/기록 흐름을 읽을 때 UI 상태 변경 로직과 snapshot 조립 로직이 섞여 보인다.

## 목표

- local command result snapshot 생성 로직을 `textual_app.presenters`로 이동한다.
- 기존 `TrinityTextualApp._local_command_snapshot()` wrapper는 유지한다.
- local command history, modal, notification 동작은 변경하지 않는다.
- 빈 body fallback `"(no output)"` 동작을 직접 테스트한다.

## 범위

- `src/trinity/textual_app/presenters.py`에 `local_command_snapshot()` 추가
- `src/trinity/textual_app/app.py`의 `_local_command_snapshot()`은 presenter 위임으로 변경
- presenter direct test 추가
- 패치 버전 업데이트

## 비목표

- local command history 보관 개수 변경
- modal/notification 표시 정책 변경
- slash command parsing 변경

## 검증

- focused: Textual app, Textual workflow controller, Textual snapshot
- full: 전체 pytest
- smoke: `trinity --version`
