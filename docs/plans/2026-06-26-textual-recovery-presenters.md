# Textual Recovery Presenter Wrapper 제거 설계

## 배경

`TrinityTextualApp`에는 execution recovery와 review repair 표시를 위해 `textual_app.presenters`를 단순 위임하는 wrapper가 남아 있다. 이 함수들은 앱 상태를 추가하지 않으므로 recovery 흐름에서 presenter를 직접 호출해 앱을 더 얇게 유지한다.

## 목표

- execution recovery와 review repair 표시 경로에서 `textual_presenters`를 직접 호출한다.
- review repair blocked ids/details/rows, execution recovery Markdown/rows wrapper를 제거한다.
- 기존 local command result, warning severity, action hint 동작은 유지한다.

## 범위

- 제거 대상 wrapper:
  - `_review_repair_blocked_ids`
  - `_review_repair_details_markdown`
  - `_review_repair_rows`
  - `_execution_recovery_markdown`
  - `_execution_recovery_rows`
- recovery 표시/repair action 호출부 변경
- 패치 버전 업데이트

## 비목표

- retry/repair action 정책 변경
- recovery 상태 계산 변경
- modal 또는 Nexus action UI 변경

## 검증

- focused: Textual app/snapshot/command parser 테스트
- full: 전체 pytest
- smoke: `trinity --version`
