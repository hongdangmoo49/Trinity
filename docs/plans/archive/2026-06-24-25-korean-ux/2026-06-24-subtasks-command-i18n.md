# Subtasks 로컬 명령 한국어 라벨 개선

## 배경

`/subtasks` 명령은 provider 내부 위임 작업을 로컬로 보여주지만, 한국어 설정에서도 빈 상태, action hint, 표 컬럼이 영어로 표시된다.

## 목표

- `subtasks_markdown()`과 `subtasks_rows()`에 `lang` 인자를 추가하고 기본 영어 동작은 유지한다.
- 한국어 설정에서 빈 상태, action hint, 표 컬럼을 한국어로 보여준다.
- subtask ID, package ID, 위임 대상, 상태, summary 원문은 번역하지 않는다.
- 앱의 `/subtasks` 처리 경로가 `config.lang`을 presenter helper에 전달하도록 연결한다.

## 설계

1. 기존 라벨 맵에 subtasks 전용 빈 상태/action hint/table column 라벨을 추가한다.
2. subtasks용 table column/action hint helper를 presenter에 둔다.
3. 앱 호출부에서 `config.lang`을 넘기고 기존 영어 기본값을 유지한다.
4. presenter 단위 테스트와 한국어 `/subtasks` 실행 경로 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "subtasks"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
