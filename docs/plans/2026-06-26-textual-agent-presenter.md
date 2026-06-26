# Textual Agent Presenter 분리 설계

## 배경

`TrinityTextualApp`는 상당수의 markdown/table row presenter를 `textual_app.presenters`로 위임하고 있다. 다만 `/agent` 세션 설정 표시에서 사용하는 session-only 안내 body와 agent table row 조립은 아직 앱 본문에 남아 있다. 이 로직은 UI 상태 변경 없이 문자열과 row tuple만 만드는 순수 presenter 성격이므로 앱에서 분리할 수 있다.

## 목표

- session-only 설정 안내 body 조립을 presenter 함수로 이동한다.
- agent 설정 테이블 row 조립을 presenter 함수로 이동한다.
- 기존 `TrinityTextualApp._session_setting_body()`와 `_agent_rows()` wrapper는 유지한다.
- `/agent` 명령 UI 출력 동작은 변경하지 않는다.

## 범위

- `src/trinity/textual_app/presenters.py`에 `session_setting_body()`, `agent_rows()` 추가
- `src/trinity/textual_app/app.py`의 기존 helper는 presenter 위임으로 변경
- 패치 버전 업데이트

## 비목표

- `/agent` 명령 동작 변경
- agent enable/disable 정책 변경
- Textual 화면 레이아웃 변경

## 검증

- focused: Textual app, Textual workflow controller, Textual snapshot
- full: 전체 pytest
- smoke: `trinity --version`
