# Execute Retry 빈 WP 경고 한국어 라벨 개선

## 배경

실행 재시도는 실행 화면 버튼과 `/execute-retry` slash command 양쪽에서 접근할 수 있다. 현재 retry할 work package가 없는 경우의 경고 본문, slash 결과 제목, action hint가 영어로 고정되어 있다.

## 목표

- 한국어 설정에서 빈 work package 경고를 한국어로 표시한다.
- `/execute-retry` 로컬 결과 제목과 action hint를 한국어로 표시한다.
- 실행 화면 retry 버튼 경고도 같은 helper를 사용한다.
- 기존 영어 기본 동작은 유지한다.

## 설계

1. `presenters.py`에 execute retry title/no-packages/action-hint helper를 추가한다.
2. 실행 화면 retry 요청 경고와 `/execute-retry` 빈 상태 결과에서 helper를 사용한다.
3. presenter와 slash command 빈 상태 경로 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "execute_presenter or execute_retry_empty or execution_retry_empty"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
