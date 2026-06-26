# Textual Session/Agent Presenter Wrapper 제거 설계

## 배경

`TrinityTextualApp`의 rounds, agent, caveman 설정 명령에는 `session_setting_body`와 `agent_rows`를 단순 위임하는 wrapper가 남아 있다. 이 wrapper는 앱 상태 변환을 하지 않으므로 호출부에서 presenter를 직접 사용하는 편이 명확하다.

## 목표

- session setting body와 agent rows wrapper를 제거한다.
- `/rounds`, `/agent`, `/caveman` 표시 경로에서 `textual_presenters`를 직접 호출한다.
- 기존 설정 변경, localized rows, action hint 동작은 유지한다.

## 범위

- 제거 대상 wrapper:
  - `_session_setting_body`
  - `_agent_rows`
- `/rounds`, `/agent`, `/caveman` 호출부 변경
- 패치 버전 업데이트

## 비목표

- 설정 명령 문법 변경
- agent enable/disable 동작 변경
- caveman 설정 정책 변경

## 검증

- focused: Textual app/snapshot/command parser 테스트
- full: 전체 pytest
- smoke: `trinity --version`
