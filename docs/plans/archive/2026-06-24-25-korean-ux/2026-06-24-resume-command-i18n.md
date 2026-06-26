# Resume 로컬 명령 한국어 라벨 개선

## 배경

`/resume` 명령은 저장된 워크플로우 목록, 빈 상태, 선택 취소, 재개 결과를 Nexus 로컬 명령 결과로 보여준다. 일부 목록 렌더링 helper는 이미 presenter에 있지만 언어 인자를 받지 않고, app 쪽 제목/힌트/표 헤더가 영어로 고정되어 있다.

## 목표

- 한국어 설정에서 `/resume` 빈 상태, 목록, 취소, 재개 결과를 한국어로 표시한다.
- archive 목록 표 헤더와 resume 결과 행 라벨을 한국어화한다.
- 기존 영어 기본 동작과 resume picker 동작은 유지한다.

## 설계

1. `presenters.py`의 resume helper에 `lang` 인자를 추가하고 title/body/action hint/table helper를 보강한다.
2. `TrinityTextualApp._handle_textual_resume_command()`와 선택 콜백에서 helper에 `config.lang`을 전달한다.
3. `resume_workflow()`에서 전달되는 provider/controller 메시지는 원문을 유지하되, title/table 라벨은 현지화한다.
4. presenter 단위 테스트와 한국어 `/resume` 빈 상태/목록/취소/성공 경로 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "resume"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
