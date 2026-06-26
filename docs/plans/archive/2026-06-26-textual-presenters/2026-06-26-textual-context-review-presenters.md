# Textual Context/Review Presenter Wrapper 제거 설계

## 배경

`TrinityTextualApp`에는 context, review, improve 표시를 위해 `textual_app.presenters`를 단순 위임하는 wrapper가 남아 있다. 앞선 presenter wrapper 제거 작업과 마찬가지로 앱이 직접 표시 흐름만 담당하도록 만들면 app 모듈을 더 얇게 유지할 수 있다.

## 목표

- `/context`, `/review`, `/improve` 경로에서 `textual_presenters`를 직접 호출한다.
- context presence check, context Markdown, review rows, improve rows wrapper를 제거한다.
- 기존 notification/local command result 동작과 localized rows를 유지한다.

## 범위

- 제거 대상 wrapper:
  - `_snapshot_has_current_context`
  - `_snapshot_context_markdown`
  - `_review_rows`
  - `_improve_rows`
- `/context`, `/review`, `/improve` 호출부 변경
- 패치 버전 업데이트

## 비목표

- review/improve 명령 처리 로직 변경
- context 표시 문구 변경
- workflow outcome 처리 변경

## 검증

- focused: Textual app/snapshot/command parser 테스트
- full: 전체 pytest
- smoke: `trinity --version`
