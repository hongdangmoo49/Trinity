# Textual Command Help Presenter Wrapper 제거 설계

## 배경

`TrinityTextualApp`의 unknown command/help 처리 경로에는 `textual_app.presenters`를 단순 위임하는 wrapper가 남아 있다. 이 함수들은 앱 상태를 사용하지 않고 slash command 흐름을 길게 만들기만 하므로 직접 presenter 호출로 정리할 수 있다.

## 목표

- unknown command와 help 표시 경로에서 `textual_presenters`를 직접 호출한다.
- 사용되지 않는 readiness label wrapper를 제거한다.
- slash command suggestion, unknown command Markdown/table rows, help Markdown/table rows 동작을 유지한다.

## 범위

- `/help` 처리부 직접 presenter 호출
- unknown command 처리부 직접 presenter 호출
- 제거 대상 wrapper:
  - `_readiness_label`
  - `_slash_command_suggestions`
  - `_unknown_command_markdown`
  - `_unknown_command_rows`
  - `_help_markdown`
  - `_help_rows`
- 패치 버전 업데이트

## 비목표

- slash command registry 변경
- unknown command 추천 알고리즘 변경
- help 문구/테이블 컬럼 변경

## 검증

- focused: Textual app/snapshot/command parser 테스트
- full: 전체 pytest
- smoke: `trinity --version`
