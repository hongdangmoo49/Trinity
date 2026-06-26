# Review 로컬 명령 한국어 라벨 개선

## 배경

`/review` 명령은 review 요청 결과 메시지가 있을 때 로컬 명령 결과를 기록하지만, 한국어 설정에서도 표 컬럼, summary 행, action hint가 영어로 표시된다.

## 목표

- `review_rows()`에 `lang` 인자를 추가하고 기본 영어 동작은 유지한다.
- 한국어 설정에서 review summary 표 행 라벨과 action hint, 표 컬럼을 한국어로 보여준다.
- workflow id, raw 상태 값, WP id, review 결과 원문은 번역하지 않는다.
- 앱의 `/review` 처리 경로가 `config.lang`을 presenter helper에 전달하도록 연결한다.
- review repair detail 표면은 별도 action 흐름이므로 이번 범위에서는 유지한다.

## 설계

1. 기존 라벨 맵에 review 전용 action hint/table/row 라벨을 추가한다.
2. review용 table column/action hint helper를 presenter에 둔다.
3. `review_rows(lang="ko")`는 행 라벨만 한국어화하고 value는 원문을 유지한다.
4. `/review` app 처리 경로에서 `config.lang`을 전달한다.
5. presenter 단위 테스트와 한국어 `/review` 실행 경로 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "review"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
