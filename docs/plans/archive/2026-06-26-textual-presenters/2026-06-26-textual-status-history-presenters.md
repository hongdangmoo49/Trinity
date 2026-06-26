# Textual Status/History Presenter Wrapper 제거 설계

## 배경

`TrinityTextualApp`에는 이미 `textual_app.presenters`로 옮긴 status, workflow, history presenter 함수들을 다시 감싸는 얇은 wrapper가 남아 있다. 이 wrapper들은 상태를 갖지 않고 단순 위임만 수행하므로 앱 본문을 길게 만들고 실제 화면 흐름을 읽기 어렵게 한다.

## 목표

- status, workflow, history slash command 호출부에서 `textual_presenters`를 직접 사용한다.
- `TrinityTextualApp`의 순수 presenter wrapper를 제거해 앱을 더 얇게 유지한다.
- 기존 Markdown/table rows 결과와 local history 결합 동작을 유지한다.

## 범위

- 제거 대상 wrapper:
  - `_snapshot_status_markdown`
  - `_snapshot_status_rows`
  - `_snapshot_workflow_markdown`
  - `_snapshot_workflow_rows`
  - `_history_rows`
  - `_history_markdown`
- `/workflow`, `/history`, `/status` 표시 경로의 호출부 변경
- 기존 presenter direct test와 Textual app focused test로 회귀 확인
- 패치 버전 업데이트

## 비목표

- status/history 표시 문구 변경
- local command result 저장 정책 변경
- Nexus 화면 갱신 방식 변경

## 검증

- focused: Textual app, Textual snapshot/presenter 관련 테스트
- full: 전체 pytest
- smoke: `trinity --version`
