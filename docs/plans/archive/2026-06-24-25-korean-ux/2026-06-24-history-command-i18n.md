# History 로컬 명령 한국어 라벨 개선

## 배경

`/history` 명령은 현재 Textual 세션에서 누적된 workflow, local command, execution log 항목을 로컬로 보여주지만, 한국어 설정에서도 빈 상태, action hint, 표 컬럼, 행/섹션 라벨이 영어로 표시된다.

## 목표

- `history_rows()`와 `history_markdown()`에 `lang` 인자를 추가하고 기본 영어 동작은 유지한다.
- 한국어 설정에서 빈 상태, action hint, 표 컬럼, 행 라벨, Markdown 섹션 라벨을 한국어로 보여준다.
- workflow id, goal, command 이름, command title, execution log 원문은 번역하지 않는다.
- 앱의 `/history` 처리 경로가 `config.lang`을 presenter helper에 전달하도록 연결한다.

## 설계

1. 기존 status/context 라벨 맵에 history 전용 빈 상태/action hint/table/section 라벨을 추가한다.
2. history용 table column/action hint helper를 presenter에 둔다.
3. `history_rows(lang="ko")`는 행 종류만 한국어화한다.
4. `history_markdown(lang="ko")`는 상단 필드와 최근 실행/로컬 항목 섹션 제목만 한국어화한다.
5. presenter 단위 테스트와 한국어 `/history` 실행 경로 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "history"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
