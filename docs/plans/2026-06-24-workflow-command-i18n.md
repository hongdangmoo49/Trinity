# Workflow 로컬 명령 한국어 라벨 개선

## 배경

`/workflow` 명령은 현재 워크플로우 요약을 에이전트 호출 없이 보여주는 로컬 명령이다. 한국어 설정에서도 Markdown 본문과 표 행이 `State`, `Pending questions`, `Post-review items`, `Execution Recovery` 같은 영어 라벨로 표시되어 `/status`, `/context`와 언어 일관성이 떨어진다.

## 목표

- `snapshot_workflow_markdown()`과 `snapshot_workflow_rows()`에 `lang` 인자를 추가하고 기본 영어 동작은 유지한다.
- 한국어 설정에서 `/workflow`의 주요 필드와 실행 복구 라벨을 한국어로 보여준다.
- 앱의 `/workflow` 처리 경로가 `config.lang`을 presenter에 전달하도록 연결한다.
- workflow id, raw 상태 값, 사용자 입력 텍스트는 임의 번역하지 않는다.

## 설계

1. 기존 status/context 라벨 helper를 재사용해 `/workflow` 라벨을 중복 없이 현지화한다.
2. 영어 기본값은 기존 문자열과 동일하게 유지한다.
3. `/workflow` table column은 기존 `status_table_columns()` helper를 사용해 한국어 설정에서 `항목/값`으로 표시한다.
4. presenter 단위 테스트와 실제 start 화면 slash command 경로 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "workflow"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
