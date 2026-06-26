# Improve 로컬 명령 한국어 라벨 개선

## 배경

`/improve` 명령은 post-review action item 적용 요청 결과를 로컬 명령 결과로 보여주지만, 한국어 설정에서도 표 컬럼, summary 행, action hint가 영어로 표시된다.

## 목표

- `improve_rows()`에 `lang` 인자를 추가하고 기본 영어 동작은 유지한다.
- 한국어 설정에서 improve summary 표 컬럼, 행 라벨, action hint를 한국어로 보여준다.
- workflow id, raw 상태 값, action item id, severity/kind/title 값은 번역하지 않는다.
- 앱의 `/improve` 처리 경로가 `config.lang`을 presenter helper에 전달하도록 연결한다.

## 설계

1. 기존 라벨 맵에 improve 전용 action hint/row 라벨을 추가한다.
2. improve용 table column/action hint helper를 presenter에 둔다.
3. `improve_rows(lang="ko")`는 행 라벨만 한국어화하고 value는 원문을 유지한다.
4. `/improve` app 처리 경로에서 `config.lang`을 전달한다.
5. presenter 단위 테스트와 한국어 `/improve` 실행 경로 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "improve"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
