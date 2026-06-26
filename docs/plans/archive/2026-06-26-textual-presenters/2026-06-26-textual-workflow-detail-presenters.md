# Textual Workflow Detail Presenter Wrapper 제거 설계

## 배경

`TrinityTextualApp`에는 questions, decisions, packages, subtasks 표시를 위해 이미 `textual_app.presenters`에 존재하는 순수 presenter 함수를 다시 감싸는 wrapper가 남아 있다. 이 wrapper는 상태를 추가하지 않고 단순 위임만 하므로 slash command 흐름을 불필요하게 길게 만든다.

## 목표

- workflow detail slash command에서 `textual_presenters`를 직접 호출한다.
- questions, decisions, packages, subtasks wrapper를 제거한다.
- 기존 localized Markdown, action hint, table rows 동작은 유지한다.

## 범위

- `/questions`, `/decisions`, `/packages`, `/subtasks` 호출부 변경
- 제거 대상 wrapper:
  - `_questions_markdown`
  - `_questions_select_markdown`
  - `_questions_rows`
  - `_decisions_markdown`
  - `_decisions_rows`
  - `_packages_markdown`
  - `_packages_rows`
  - `_subtasks_markdown`
  - `_subtasks_rows`
- 패치 버전 업데이트

## 비목표

- slash command 문법 변경
- 화면 문구/테이블 컬럼 변경
- workflow snapshot 구조 변경

## 검증

- focused: Textual app/snapshot/presenter 관련 테스트
- full: 전체 pytest
- smoke: `trinity --version`
