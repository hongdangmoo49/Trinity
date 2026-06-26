# Decisions 로컬 명령 한국어 라벨 개선

## 배경

`/decisions` 명령은 현재 세션의 결정 목록을 로컬로 보여주지만, 한국어 설정에서도 빈 상태, action hint, 표 컬럼이 영어로 표시된다. 질문/워크플로우 로컬 명령과 같은 수준의 한국어 UX가 필요하다.

## 목표

- `decisions_markdown()`과 `decisions_rows()` 호출 경로에 `lang` 인자를 추가하고 기본 영어 동작은 유지한다.
- 한국어 설정에서 빈 상태와 action hint, 표 컬럼을 한국어로 보여준다.
- 결정 본문은 사용자/에이전트가 만든 원자료이므로 번역하지 않는다.
- 앱의 `/decisions` 처리 경로가 `config.lang`을 presenter helper에 전달하도록 연결한다.

## 설계

1. 기존 status/context 라벨 맵에 decisions 전용 빈 상태/action hint/table column 라벨을 추가한다.
2. decisions용 table column/action hint helper를 presenter에 둔다.
3. `/decisions` app 처리 경로에서 `config.lang`을 전달한다.
4. presenter 단위 테스트와 한국어 `/decisions` 실행 경로 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "decisions"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
