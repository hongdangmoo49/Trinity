# Packages 로컬 명령 한국어 라벨 개선

## 배경

`/packages` 명령은 blueprint/local WP 그래프의 패키지를 로컬로 보여주지만, 한국어 설정에서도 빈 상태, action hint, 표 컬럼, source 값이 영어로 표시된다.

## 목표

- `packages_markdown()`과 `packages_rows()`에 `lang` 인자를 추가하고 기본 영어 동작은 유지한다.
- 한국어 설정에서 빈 상태, action hint, 표 컬럼, source 값을 한국어로 보여준다.
- package 본문은 원자료로 유지한다.
- 앱의 `/packages` 처리 경로가 `config.lang`을 presenter helper에 전달하도록 연결한다.

## 설계

1. 기존 라벨 맵에 packages 전용 빈 상태/action hint/table column/source 라벨을 추가한다.
2. packages용 table column/action hint helper를 presenter에 둔다.
3. `packages_rows(lang="ko")`는 source 값을 `중앙`, `로컬`로 표시한다.
4. presenter 단위 테스트와 한국어 `/packages` 실행 경로 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "packages"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
