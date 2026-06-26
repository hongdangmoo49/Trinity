# Agent 로컬 명령 한국어 라벨 개선

## 배경

`/agent` 명령은 현재 에이전트 활성화 상태 조회와 세션 한정 on/off 변경을 로컬 명령 결과로 보여준다. 한국어 설정에서도 제목, 본문, action hint, 표 헤더, enabled 값이 영어로 고정되어 있다.

## 목표

- 한국어 설정에서 `/agent` 조회/변경/사용법 오류/알 수 없는 에이전트 결과를 한국어로 표시한다.
- Agent 테이블의 `Agent`, `Enabled`, `Provider` 헤더와 enabled 값을 한국어화한다.
- 기존 영어 기본 동작과 세션 한정 설정 로직은 유지한다.

## 설계

1. `presenters.py`에 agent 전용 title/body/action hint/table helper를 추가한다.
2. `_agent_rows()`가 언어를 받아 enabled 값을 `yes/no` 또는 `예/아니오`로 렌더링하도록 변경한다.
3. `TrinityTextualApp._handle_textual_agent_command()`에서 helper에 `config.lang`을 전달한다.
4. presenter 단위 테스트와 한국어 `/agent` 조회/변경/오류 경로 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "agent"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
