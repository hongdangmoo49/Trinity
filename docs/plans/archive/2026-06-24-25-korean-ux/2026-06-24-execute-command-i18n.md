# Execute 로컬 명령 한국어 라벨 개선

## 배경

`/execute` 명령은 planning이 끝나기 전 실행 요청이 들어오거나, 이전 실행이 중단되어 recovery가 필요한 경우 Nexus 로컬 명령 결과를 보여준다. 현재 한국어 설정에서도 execute 오류 제목/action hint와 execution recovery 제목/힌트/표 헤더가 영어로 고정되어 있다.

## 목표

- 한국어 설정에서 `/execute` 사전 조건 오류 제목과 action hint를 한국어로 표시한다.
- execution recovery 로컬 결과의 제목, action hint, 표 헤더를 한국어로 표시한다.
- recovery 상세 markdown/rows는 기존 presenter의 언어 지원 경로를 사용한다.
- 워크플로우 실행 요청, recovery 판단, retry 동작은 변경하지 않는다.

## 설계

1. `presenters.py`에 execute title/action hint와 execution recovery title/action hint/table helper를 추가한다.
2. `_handle_textual_slash_command()`의 `/execute` 오류 기록에서 helper에 `config.lang`을 전달한다.
3. `_present_execution_recovery()`에서 recovery markdown/rows와 제목/힌트/표 헤더에 `config.lang`을 전달한다.
4. presenter 단위 테스트와 한국어 `/execute` 오류/recovery 경로 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "execute"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
