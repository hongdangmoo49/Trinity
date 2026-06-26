# Textual Ask Command Parser 분리 설계

## 배경

`TrinityTextualApp._parse_ask_args()`는 `/ask` 명령의 대상 agent, model override, prompt, 오류 메시지를 계산하는 순수 parsing helper다. 현재 앱 본문에 남아 있어 `/ask` 실행 흐름을 읽을 때 parsing 규칙과 화면 전환/워크플로우 호출 로직이 섞여 보인다.

## 목표

- `/ask` 인자 parsing을 `textual_app.command_parsers`로 분리한다.
- 기존 `TrinityTextualApp._parse_ask_args()` 반환 형태는 유지한다.
- 오류 메시지 localization, `all` selector, comma-separated target selector, `--model/-m` 동작을 유지한다.
- parser direct test를 추가해 앱 없이 parsing 규칙을 검증한다.

## 범위

- 신규 모듈: `src/trinity/textual_app/command_parsers.py`
- `AskCommandParseResult` dataclass와 `parse_ask_args()` 추가
- `TrinityTextualApp._parse_ask_args()`는 새 parser로 위임
- parser direct test 추가
- 패치 버전 업데이트

## 비목표

- `/ask` 명령 문법 변경
- target agent 선택 UI 변경
- workflow start/follow-up 실행 흐름 변경

## 검증

- focused: Textual command parser, Textual app, Textual workflow controller
- full: 전체 pytest
- smoke: `trinity --version`
