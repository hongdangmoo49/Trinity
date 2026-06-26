# Textual Resume Presenter Wrapper 제거 설계

## 배경

`TrinityTextualApp`의 `/resume` 처리에는 resume archive/result 표시를 위해 `textual_app.presenters`를 단순 위임하는 wrapper가 남아 있다. 이 wrapper는 상태를 갖지 않으므로 직접 presenter 호출로 정리할 수 있다.

## 목표

- `/resume` archive 목록과 resume 결과 표시 경로에서 `textual_presenters`를 직접 호출한다.
- resume archive Markdown/rows, resume result rows wrapper를 제거한다.
- 기존 resume modal, local command result, localized table rows 동작은 유지한다.

## 범위

- 제거 대상 wrapper:
  - `_resume_archives_markdown`
  - `_resume_archive_rows`
  - `_resume_result_rows`
- `/resume` 호출부 변경
- 패치 버전 업데이트

## 비목표

- resume selector 문법 변경
- resume modal 동작 변경
- workflow resume 처리 변경

## 검증

- focused: Textual app/snapshot/command parser 테스트
- full: 전체 pytest
- smoke: `trinity --version`
