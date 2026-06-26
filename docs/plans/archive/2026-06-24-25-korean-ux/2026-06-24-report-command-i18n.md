# Report 로컬 명령 한국어 라벨 개선

## 배경

`/report` 명령은 Nexus에서 리포트 화면을 열거나 `/report save`로 Markdown 리포트를 저장한다. 리포트 화면 자체의 chrome 라벨은 한국어를 지원하지만, Nexus 로컬 명령 결과의 제목, 빈 상태 안내, 저장 결과, 표 헤더와 행 라벨은 영어로 고정되어 있다.

## 목표

- 한국어 설정에서 `/report` 결과 메시지와 action hint를 한국어로 표시한다.
- `/report save` 저장 결과의 표 헤더와 path 행 라벨을 한국어로 표시한다.
- 리포트 화면을 여는 정상 경로의 요약 행 라벨을 한국어로 표시한다.
- 기존 영어 기본 동작과 Markdown 리포트 내용은 유지한다.

## 설계

1. `presenters.py`의 status context label map에 report 전용 라벨과 메시지를 추가한다.
2. report title, 빈 상태 메시지, 저장 완료 메시지, action hint, table row 생성 helper를 둔다.
3. `TrinityTextualApp._handle_textual_report_command()`에서 고정 문자열 대신 helper에 `config.lang`을 전달한다.
4. presenter 단위 테스트와 한국어 `/report`, `/report save` 실행 경로 테스트를 추가한다.

## 테스트

- `uv run pytest tests/test_textual_app.py -k "report"`
- `uv run pytest tests/test_textual_app.py`
- `uv run pytest`
- `git diff --check`
- `uv run trinity --version`
